"""One probe per data source. A probe returns a short description on success and raises on failure,
so the same functions serve the laptop runner (probes/run_probes.py) and GET /debug/sources."""
from __future__ import annotations

import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Callable

import requests

from app.core.http import fetch
from app.core.timeutil import now_ist
from app.sources import bse, nse, prices, symbols

PDF_CAP = 5 * 1024 * 1024  # probes only need to prove the download works
SCREENER_UA = bse.HEADERS["User-Agent"]


@dataclass
class ProbeResult:
    name: str
    ok: bool
    ms: int
    detail: str


def _bse_code(symbol: str) -> str:
    listing = symbols.resolve(symbol)
    if listing is None:
        raise LookupError(f"{symbol} is not on NSE's equity list")
    if not listing.bse_code:
        raise LookupError(f"{symbol} has no BSE scrip (ISIN {listing.isin} is not in BSE's scrip master)")
    return listing.bse_code


def yfinance_prices(symbol: str) -> str:
    history = prices.fetch_history(symbol)
    last = history.bars[-1]
    return f"{history.yahoo_symbol}: {len(history.bars)} daily bars, last {last.day} close {last.close:,.2f}"


def yfinance_quarterly(symbol: str) -> str:
    quarters = prices.quarterly_financials(symbol)
    if not quarters:
        raise RuntimeError("no quarterly income statement")
    latest = quarters[0]
    return (
        f"{len(quarters)} quarters, latest {latest.period_end}: revenue {latest.revenue_cr} Cr, "
        f"EBITDA {latest.ebitda_cr}, PBT {latest.pbt_cr}, net income {latest.net_income_cr}"
    )


def symbol_mapping(symbol: str) -> str:
    listing = symbols.resolve(symbol, refresh=True)
    if listing is None:
        raise LookupError(f"{symbol} is not on NSE's equity list")
    where = f"BSE scrip {listing.bse_code}" if listing.bse_code else "no BSE scrip (NSE only)"
    return f"{listing.symbol} -> {listing.isin} -> {where}"


def bse_announcements(symbol: str) -> str:
    today = now_ist().date()
    rows = bse.fetch_window(_bse_code(symbol), today - timedelta(days=7), today)
    top = Counter(a.category for a in rows).most_common(2)
    return f"{len(rows)} announcements in 7 days; top categories {top}" if rows else "0 announcements in 7 days"


def bse_transcripts(symbol: str) -> str:
    today = now_ist().date()
    rows = bse.fetch_window(_bse_code(symbol), today - timedelta(days=364), today)
    found = [a for a in rows if bse.is_transcript(a)]
    latest = f", latest {found[0].published_at:%Y-%m-%d}" if found else ""
    return f"{len(found)} transcripts in the last 365 days (of {len(rows)} announcements){latest}"


def bse_pdf_download(symbol: str) -> str:
    today = now_ist().date()
    rows = bse.fetch_window(_bse_code(symbol), today - timedelta(days=120), today)
    target = next((a for a in rows if a.attachment_url and (bse.is_transcript(a) or bse.is_results(a))), None)
    if target is None:
        raise LookupError("no results or transcript PDF in the last 120 days")
    name = target.attachment_url.rsplit("/", 1)[-1]
    headers = {**bse.HEADERS, "Accept": "application/pdf,*/*"}
    for base in bse.ATTACHMENT_BASES:
        started = time.time()
        resp = fetch(base + name, headers=headers, max_bytes=PDF_CAP, timeout=(10, 30))
        if resp.ok:
            if not resp.content.startswith(b"%PDF"):
                raise RuntimeError("response is not a PDF")
            return f"{name[:8]}.. {len(resp.content) // 1024} KB in {time.time() - started:.1f}s via {base.split('/')[-2]}"
    raise RuntimeError("PDF not found on AttachLive or AttachHis")


def nse_announcements(symbol: str) -> str:
    today = now_ist().date()
    rows = nse.fetch_announcements(symbol, today - timedelta(days=7), today)
    top = Counter(a.category for a in rows).most_common(2)
    return f"{len(rows)} announcements in 7 days; top descriptions {top}" if rows else "0 announcements in 7 days"


def screener_page(symbol: str) -> str:
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    resp = fetch(url, headers={"User-Agent": SCREENER_UA, "Accept": "text/html"}, timeout=(10, 30))
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status}")
    links = re.findall(r'href="([^"]+)"[^>]*>\s*Transcript', resp.text(), re.I)
    return f"page ok ({len(resp.content) // 1024} KB), {len(links)} transcript links"


PROBES: dict[str, Callable[[str], str]] = {
    "yfinance_prices": yfinance_prices,
    "yfinance_quarterly": yfinance_quarterly,
    "symbol_mapping": symbol_mapping,
    "bse_announcements": bse_announcements,
    "bse_transcripts": bse_transcripts,
    "bse_pdf_download": bse_pdf_download,
    "nse_announcements": nse_announcements,
    "screener_page": screener_page,
}


def run_probe(name: str, symbol: str) -> ProbeResult:
    started = time.time()
    try:
        detail, ok = PROBES[name](symbol), True
    except Exception as exc:  # a probe must report any failure, not raise it
        detail, ok = f"{type(exc).__name__}: {str(exc)[:200]}", False
    return ProbeResult(name, ok, int((time.time() - started) * 1000), detail)


def run_all(symbol: str, workers: int = 4) -> list[ProbeResult]:
    """symbol_mapping first (the BSE probes need its cache), then everything else side by side."""
    results = {"symbol_mapping": run_probe("symbol_mapping", symbol)}
    rest = [name for name in PROBES if name != "symbol_mapping"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(lambda n: run_probe(n, symbol), rest):
            results[result.name] = result
    return [results[name] for name in PROBES]


def report(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "generated_at": now_ist().isoformat(timespec="seconds"),
        "results": [asdict(r) for r in run_all(symbol)],
    }
