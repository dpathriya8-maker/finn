"""BSE announcements JSON API client (verified from a laptop in Step 3)."""
from __future__ import annotations

import re
import time
from datetime import date, timedelta
from typing import Any

import requests

from app.core.http import BlockedUrl, Fetched, FetchError, fetch
from app.core.timeutil import parse_ist
from app.sources.models import Announcement

API = "https://api.bseindia.com/BseIndiaAPI/api"
ANNOUNCEMENTS_URL = f"{API}/AnnSubCategoryGetData/w"
ATTACHMENT_BASES = (
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/",
    "https://www.bseindia.com/xml-data/corpfiling/AttachHis/",  # older filings move here
)

# BSE answers 403 "Access Denied" unless all four of these are present (User-Agent and Referer
# alone are not enough).
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
    "Accept": "application/json, text/plain, */*",
}

MAX_SPAN_DAYS = 364  # a single request may cover at most 365 days; 366 returns HTTP 400
PAGE_SIZE = 50  # rows per page; ROWCNT in Table1 is the total
REQUEST_DELAY_S = 0.25  # we are a guest on someone else's production API: one request at a time
_COMPANY_PREFIX = re.compile(r"^.{1,120}? - \d{5,6} - ")  # "<Company> - <scrip code> - <subject>"


def clean_subject(subject: str | None) -> str:
    return _COMPANY_PREFIX.sub("", (subject or "").strip(), count=1)


def parse_row(row: dict[str, Any]) -> Announcement:
    """Turn one BSE `Table` row into an Announcement."""
    attachment = (row.get("ATTACHMENTNAME") or "").strip()
    size = str(row.get("Fld_Attachsize") or "").strip()
    return Announcement(
        source="bse",
        id=str(row["NEWSID"]),
        company=(row.get("SLONGNAME") or "").strip(),
        symbol=str(row.get("SCRIP_CD") or "").strip(),
        category=(row.get("CATEGORYNAME") or "").strip(),
        subcategory=(row.get("SUBCATNAME") or "").strip(),
        subject=clean_subject(row.get("NEWSSUB")),
        body=(row.get("HEADLINE") or row.get("MORE") or "").strip(),
        published_at=parse_ist(row.get("NEWS_DT") or row["DT_TM"]),
        attachment_url=ATTACHMENT_BASES[0] + attachment if attachment else None,
        attachment_bytes=int(size) if size.isdigit() else None,
    )


def is_transcript(a: Announcement) -> bool:
    """Concall transcripts are filed under 'Earnings Call Transcript', but some companies (for example
    Bajaj Finance, and Reliance once) file them under 'Analyst / Investor Meet', so the text decides too."""
    return a.subcategory == "Earnings Call Transcript" or "transcript" in f"{a.subject} {a.body}".lower()


def is_results(a: Announcement) -> bool:
    return a.category == "Result"


RETRY_STATUSES = {400, 429, 500, 502, 503, 504}  # BSE answers a valid request with 400 now and then
RETRY_DELAYS_S = (1.0, 3.0)  # so at most three attempts, with a pause. A 403 (blocked) is never retried.


def _get(session: requests.Session, params: dict[str, Any]) -> Fetched:
    problem = "no attempt made"
    for pause in (0.0, *RETRY_DELAYS_S):
        if pause:
            time.sleep(pause)
        try:
            resp = fetch(ANNOUNCEMENTS_URL, session=session, headers=HEADERS, params=params, timeout=(10, 30))
        except BlockedUrl:
            raise
        except FetchError as exc:  # connection reset, timeout
            problem = str(exc)
            continue
        if resp.ok:
            return resp
        problem = f"HTTP {resp.status}"
        if resp.status not in RETRY_STATUSES:
            break
    raise FetchError(f"BSE announcements failed: {problem}")


def fetch_window(
    scrip_code: str, start: date, end: date, *, session: requests.Session | None = None, delay: float = REQUEST_DELAY_S
) -> list[Announcement]:
    """All announcements for one scrip between two dates (at most 365 days apart), newest first."""
    if (end - start).days > MAX_SPAN_DAYS:
        raise ValueError("BSE accepts at most 365 days per request; use fetch_announcements")
    http = session or requests.Session()
    rows: dict[str, dict[str, Any]] = {}  # by NEWSID: a new filing landing mid-read can shift a row onto two pages
    page = 1
    while page <= 100:
        params = {
            "pageno": page,
            "strCat": "-1",
            "strPrevDate": start.strftime("%Y%m%d"),
            "strScrip": scrip_code,
            "strSearch": "P",
            "strToDate": end.strftime("%Y%m%d"),
            "strType": "C",
            "subcategory": "-1",
        }
        body = _get(http, params).json()
        table = body.get("Table") or []
        total = ((body.get("Table1") or [{}])[0]).get("ROWCNT")
        if not table:
            break
        before = len(rows)
        rows.update({row["NEWSID"]: row for row in table})
        if len(rows) == before or (total is not None and len(rows) >= int(total)):
            break  # nothing new on this page, or we have them all
        page += 1
        time.sleep(delay)
    return sorted((parse_row(r) for r in rows.values()), key=lambda a: a.published_at, reverse=True)


def fetch_announcements(
    scrip_code: str, start: date, end: date, *, session: requests.Session | None = None, delay: float = REQUEST_DELAY_S
) -> list[Announcement]:
    """Like fetch_window, but any span: it is split into 365-day requests, newest window first."""
    http = session or requests.Session()
    found: dict[str, Announcement] = {}
    high = end
    while high >= start:
        low = max(start, high - timedelta(days=MAX_SPAN_DAYS))
        for a in fetch_window(scrip_code, low, high, session=http, delay=delay):
            found[a.id] = a
        high = low - timedelta(days=1)
        if high >= start:
            time.sleep(delay)
    return sorted(found.values(), key=lambda a: a.published_at, reverse=True)
