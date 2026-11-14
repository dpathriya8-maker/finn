"""NSE corporate announcements API client. Works from a laptop with a normal browser-style session."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import requests

from app.core.http import FetchError, fetch
from app.core.security import TICKER_RE
from app.core.timeutil import parse_ist
from app.sources.models import Announcement

HOME = "https://www.nseindia.com/"
ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements"
REFERER = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
PAGE_HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"}
API_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": REFERER,
}

_SIZE = re.compile(r"^\s*([\d.]+)\s*(B|KB|MB|GB)?\s*$", re.I)
_UNIT = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}


def parse_size(text: str | None) -> int | None:
    """'306.78 KB' -> bytes."""
    match = _SIZE.match(text or "")
    if not match:
        return None
    return int(float(match.group(1)) * _UNIT[(match.group(2) or "B").upper()])


def parse_row(row: dict[str, Any]) -> Announcement:
    """Turn one NSE announcement record into an Announcement."""
    desc = (row.get("desc") or "").strip()
    file_url = (row.get("attchmntFile") or "").strip()
    return Announcement(
        source="nse",
        id=str(row.get("seq_id") or ""),
        company=(row.get("sm_name") or "").strip(),
        symbol=(row.get("symbol") or "").strip(),
        category=desc,
        subcategory="",
        subject=desc,
        body=(row.get("attchmntText") or "").strip(),
        published_at=parse_ist(row["an_dt"], "%d-%b-%Y %H:%M:%S"),
        attachment_url=file_url if file_url.startswith("https://") else None,
        attachment_bytes=parse_size(row.get("fileSize")),
    )


def fetch_announcements(
    symbol: str, start: date, end: date, *, session: requests.Session | None = None
) -> list[Announcement]:
    """Announcements for an NSE symbol between two dates, newest first. NSE needs the cookies from its
    home page first; without a date range it returns the company's whole history (megabytes)."""
    if not TICKER_RE.fullmatch(symbol):
        raise ValueError(f"invalid NSE symbol: {symbol!r}")
    http = session or requests.Session()
    fetch(HOME, session=http, headers=PAGE_HEADERS, timeout=(10, 20))
    resp = fetch(
        ANNOUNCEMENTS_URL,
        session=http,
        headers=API_HEADERS,
        params={
            "index": "equities",
            "symbol": symbol,
            "from_date": start.strftime("%d-%m-%Y"),
            "to_date": end.strftime("%d-%m-%Y"),
        },
        timeout=(10, 30),
    )
    if not resp.ok:
        raise FetchError(f"NSE announcements returned HTTP {resp.status}")
    body = resp.json()
    rows = body if isinstance(body, list) else body.get("data", [])
    unique = {a.id: a for a in (parse_row(r) for r in rows)}
    return sorted(unique.values(), key=lambda a: a.published_at, reverse=True)
