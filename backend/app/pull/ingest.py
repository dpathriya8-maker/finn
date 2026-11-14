"""Find a company's concall transcripts and latest annual report on the exchanges, download them through the safe fetch
(allow-list, 25 MB cap) and read their text. The only sources are primary documents the company itself filed.

A document is downloaded and read once: its pages are kept in the cache under its URL.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from app.core.cache import Cache
from app.core.http import MAX_BYTES
from app.core.timeutil import now_ist
from app.push.results_card import fiscal_label, parse_date
from app.sources import bse, documents, nse, symbols
from app.sources.models import Announcement, Listing

LOOKBACK_DAYS = 430  # about 14 months: the last four calls, even when one is slow to be filed
TRANSCRIPTS_WANTED = 4
MAX_PAGES = 700  # an annual report is a few hundred pages; more than this is read only up to here
MIN_TEXT_PER_PAGE = 120  # fewer characters per page on average means a scan with no text layer
MIN_REPORT_PAGES = 20  # a "report" shorter than this is a notice or a letter that points to the report
CACHE_VERSION = "v1"


@dataclass
class Document:
    id: str  # "d1", oldest first; the annual report comes last
    kind: str  # "transcript" or "annual_report"
    title: str
    period: str | None  # "Q2 FY27" for a call, "FY26" for an annual report
    date: str  # the day it was filed, ISO
    url: str
    bytes: int
    sha256: str
    pages: list[str] = field(default_factory=list)  # page 1 is pages[0]; the PDF's own numbering


@dataclass
class Corpus:
    symbol: str
    name: str
    documents: list[Document]
    warnings: list[str] = field(default_factory=list)


@dataclass
class IngestSources:
    """The outside world, injectable so tests never touch the network."""

    resolve: Callable[[str], Listing | None] = symbols.resolve
    bse_announcements: Callable[..., list[Announcement]] = bse.fetch_announcements
    nse_announcements: Callable[..., list[Announcement]] = nse.fetch_announcements
    pdf: Callable[[str], bytes] = documents.fetch_pdf
    cache: Cache | None = None
    today: Callable[[], date] = lambda: now_ist().date()
    corpus_dir: Path | None = None  # a folder of saved corpora (the demo companies), checked before the exchanges are


class NoDocuments(Exception):
    """The company could not be found, or has nothing to read. `reason` is safe to show."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ------------------------------------------------------------------------------------------------ labels
_Q_FY = re.compile(r"\bQ\s?([1-4])\s*[-\s]?\s*(?:FY|F\.Y\.?)\s*'?\s*(\d{2,4})(?:\s*[-–/]\s*(\d{2,4}))?", re.I)


_QUARTER_ENDED = re.compile(r"\bquarter\s+ended(?:\s+on)?\s+(.{0,30})", re.I)
_HELD_ON = re.compile(r"\b(?:held|conducted)\s+on\s+(.{0,40})", re.I)
_QUARTER_ENDS = ((3, 31), (6, 30), (9, 30), (12, 31))
CALL_TO_FILING_DAYS = 10  # SEBI wants a transcript filed within five working days of the call


def quarter_end_before(day: date) -> date:
    """The last quarter-end strictly before a day: a call is about the quarter that had just ended."""
    return max(date(y, m, d) for y in (day.year - 1, day.year) for m, d in _QUARTER_ENDS if date(y, m, d) < day)


def _is_quarter_end(day: date) -> bool:
    return any(abs((day - date(day.year + shift, m, d)).days) <= 3 for shift in (0, 1) for m, d in _QUARTER_ENDS if shift == 0 or m == 3)


def quarter_from_text(text: str) -> str | None:
    """A quarter the text itself names: "Q1 FY27", "Q1 FY2026-27", "Q2 FY 2026 - 2027", or "quarter ended 30 June 2026".
    A date that is merely somewhere in the text is NOT used: in a transcript it is the day of the call, not a quarter-end."""
    match = _Q_FY.search(text)
    if match:
        year = match.group(3) or match.group(2)
        return f"Q{match.group(1)} FY{year[-2:]}"
    ended = _QUARTER_ENDED.search(text)
    day = parse_date(ended.group(1)) if ended else None
    return fiscal_label(day) if day and _is_quarter_end(day) else None


def quarter_for(a: Announcement) -> str:
    """The quarter a call is about. The text's own label wins. Otherwise the quarter that ended just before the call:
    the call's date if the filing gives one close to the filing day (a typo such as 29 June for 29 July is then
    ignored), else the day it was filed."""
    text = f"{a.subject} {a.body}"
    explicit = quarter_from_text(text)
    if explicit:
        return explicit
    filed = a.published_at.date()
    held = _HELD_ON.search(text)
    called = parse_date(held.group(1)) if held else None
    day = called if called and 0 <= (filed - called).days <= CALL_TO_FILING_DAYS else filed
    return fiscal_label(quarter_end_before(day))


def _quarter_order(label: str) -> tuple[int, int]:
    match = re.match(r"Q([1-4]) FY(\d{2})", label)
    return (int(match.group(2)), int(match.group(1))) if match else (0, 0)


# ------------------------------------------------------------------------------------------------ discovery
def _is_pdf(a: Announcement) -> bool:
    return bool(a.attachment_url) and a.attachment_url.lower().split("?")[0].endswith(".pdf")


def _is_transcript(a: Announcement) -> bool:
    if a.source == "bse":
        return bse.is_transcript(a)
    return "transcript" in f"{a.subject} {a.body}".lower()


def _is_annual_report(a: Announcement) -> bool:
    return "annual report" in f"{a.subcategory} {a.subject}".lower() if a.source == "bse" else "annual report" in f"{a.category} {a.subject}".lower()


def discover(symbol: str, listing: Listing, sources: IngestSources) -> tuple[list[Announcement], list[str]]:
    """Every announcement of the last 14 months, from BSE when the company has a scrip code and from NSE otherwise."""
    today = sources.today()
    start = today - timedelta(days=LOOKBACK_DAYS)
    warnings: list[str] = []
    attempts = []
    if listing.bse_code:
        attempts.append(("BSE", lambda: sources.bse_announcements(listing.bse_code, start, today)))
    attempts.append(("NSE", lambda: sources.nse_announcements(symbol, start, today)))
    for name, fetch in attempts:
        try:
            return fetch(), warnings
        except Exception as exc:  # the exchange was unreachable: try the other one
            warnings.append(f"{name} announcements could not be fetched ({type(exc).__name__}).")
    raise NoDocuments("Neither exchange could be reached for this company's filings just now. Try again in a few minutes.")


def pick(announcements: list[Announcement]) -> tuple[list[tuple[str, Announcement]], Announcement | None]:
    """The last four calls (one per quarter, the biggest file if a quarter has several) and the latest annual report."""
    by_quarter: dict[str, tuple[str, Announcement]] = {}
    for a in announcements:
        if not (_is_transcript(a) and _is_pdf(a)):
            continue
        label = quarter_for(a)
        held = by_quarter.get(label)
        if held is None or (a.attachment_bytes or 0) > (held[1].attachment_bytes or 0):
            by_quarter[label] = (label, a)
    calls = sorted(by_quarter.values(), key=lambda item: _quarter_order(item[0]))[-TRANSCRIPTS_WANTED:]
    return calls, pick_report(announcements)


def pick_report(announcements: list[Announcement]) -> Announcement | None:
    """The annual report: the biggest filing of the latest annual-report cycle. A company files the report itself and, the
    same day, a covering letter or an AGM notice that mentions it; the letter is small, so taking the last filing
    listed would pick the letter."""
    reports = [a for a in announcements if _is_annual_report(a) and _is_pdf(a)]
    if not reports:
        return None
    newest = max(a.published_at for a in reports)
    cycle = [a for a in reports if (newest - a.published_at).days <= 45]
    return max(cycle, key=lambda a: a.attachment_bytes or 0)


# ------------------------------------------------------------------------------------------------ reading
def read_pages(pdf: bytes) -> list[str]:
    import pymupdf  # imported here so the API starts fast

    document = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        return [document[i].get_text("text") for i in range(min(document.page_count, MAX_PAGES))]
    finally:
        document.close()


def _cache_key(url: str) -> str:
    return f"doc:{CACHE_VERSION}:{hashlib.sha256(url.encode()).hexdigest()}"


def load(a: Announcement, *, kind: str, title: str, period: str | None, sources: IngestSources) -> Document | str:
    """The document with its pages, from the cache or downloaded and read. Returns a reason (a string) when it cannot be used."""
    url = a.attachment_url or ""
    stored: Any = sources.cache.get(_cache_key(url)) if sources.cache is not None else None
    if isinstance(stored, dict) and stored.get("pages"):
        return Document(id="", kind=kind, title=title, period=period, date=a.published_at.date().isoformat(), url=url, bytes=stored["bytes"], sha256=stored["sha256"], pages=stored["pages"])
    try:
        data = sources.pdf(url)
        pages = read_pages(data)
    except Exception as exc:
        return f"{title} could not be downloaded or read ({type(exc).__name__})."
    if not pages or sum(len(p.strip()) for p in pages) < MIN_TEXT_PER_PAGE * len(pages):
        return f"{title} is a scan with no text layer, so it cannot be searched."
    digest = hashlib.sha256(data).hexdigest()
    if sources.cache is not None:
        sources.cache.set(_cache_key(url), {"bytes": len(data), "sha256": digest, "pages": pages})
    return Document(id="", kind=kind, title=title, period=period, date=a.published_at.date().isoformat(), url=url, bytes=len(data), sha256=digest, pages=pages)


def ingest(symbol: str, sources: IngestSources | None = None, *, progress: Callable[[str], None] = lambda _m: None) -> Corpus:
    """Everything primary FINN can read about a company: the last four concall transcripts and the latest annual
    report. Raises NoDocuments, with a reason fit to show, when there is nothing."""
    sources = sources or IngestSources()
    if sources.corpus_dir is not None:
        from app.pull import corpus_store  # local: corpus_store imports this module

        saved = corpus_store.load(symbol, sources.corpus_dir)
        if saved is not None:
            progress("Reading the saved documents")
            return saved
    progress("Finding the company")
    listing = sources.resolve(symbol)
    if listing is None:
        raise NoDocuments(f"{symbol} is not on NSE's list of equities.")
    progress("Looking for concall transcripts and the annual report")
    announcements, warnings = discover(symbol, listing, sources)
    calls, report = pick(announcements)
    if not calls and report is None:
        raise NoDocuments("No concall transcripts or annual report were found among this company's filings of the last 14 months.")

    loaded: list[Document] = []
    for label, a in calls:
        progress(f"Reading the {label} call")
        doc = load(a, kind="transcript", title=f"{label} earnings call transcript", period=label, sources=sources)
        if isinstance(doc, str):
            warnings.append(doc)
        else:
            loaded.append(doc)
    if len(calls) < TRANSCRIPTS_WANTED:
        warnings.append(f"Only {len(calls)} concall transcript{'' if len(calls) == 1 else 's'} {'was' if len(calls) == 1 else 'were'} found in the last 14 months, not {TRANSCRIPTS_WANTED}.")
    if report is not None:
        if (report.attachment_bytes or 0) > MAX_BYTES:
            warnings.append("The latest annual report is larger than the 25 MB limit and was not read.")
        else:
            progress("Reading the annual report")
            year = report.published_at.year if report.published_at.month >= 4 else report.published_at.year - 1
            # A report filed from April to December covers the financial year that ended that March; one filed in January to March, the one before.
            doc = load(report, kind="annual_report", title=f"Annual report FY{year % 100:02d}", period=f"FY{year % 100:02d}", sources=sources)
            if isinstance(doc, str):
                warnings.append(doc)
            elif len(doc.pages) < MIN_REPORT_PAGES:
                warnings.append(f"The annual-report filing is only {len(doc.pages)} pages long (a notice, not the report), so it was not used.")
            else:
                loaded.append(doc)
    else:
        warnings.append("No annual report was found among the filings of the last 14 months.")
    if not loaded:
        raise NoDocuments("The documents were found but none could be read. " + " ".join(warnings))
    for number, doc in enumerate(loaded, start=1):
        doc.id = f"d{number}"
    return Corpus(symbol=symbol, name=listing.name if hasattr(listing, "name") else symbol, documents=loaded, warnings=warnings)
