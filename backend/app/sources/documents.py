"""Download a filing's PDF through the safe fetch: allow-listed hosts only, a 25 MB cap, redirects re-checked."""
from __future__ import annotations

from typing import Callable
from urllib.parse import urlparse

from app.core.http import Fetched, FetchError, fetch
from app.sources import bse, nse

PDF_TIMEOUT = (10, 90)  # connect, read: a results filing can be 15 MB
_LIVE, _HISTORY = bse.ATTACHMENT_BASES


def _headers(url: str) -> dict[str, str]:
    """Each exchange wants its own browser-like headers (BSE refuses a request without all four)."""
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("bseindia.com"):
        return {**bse.HEADERS, "Accept": "application/pdf,*/*"}
    return {"User-Agent": nse.UA, "Accept": "application/pdf,*/*", "Referer": nse.REFERER}


def candidate_urls(url: str) -> list[str]:
    """A BSE attachment sits under AttachLive for a while and then moves to AttachHis, so a missing file is
    looked for in both. Any other URL is used as it is."""
    if url.startswith(_LIVE):
        return [url, _HISTORY + url[len(_LIVE) :]]
    if url.startswith(_HISTORY):
        return [url, _LIVE + url[len(_HISTORY) :]]
    return [url]


def fetch_pdf(url: str, *, get: Callable[..., Fetched] = fetch) -> bytes:
    """The filing's bytes, checked to really be a PDF. Raises FetchError (BlockedUrl, TooLarge are kinds of it)
    when the file cannot be had, so the caller can say why there is no card."""
    problems: list[str] = []
    for candidate in candidate_urls(url):
        response = get(candidate, headers=_headers(candidate), timeout=PDF_TIMEOUT)
        if response.ok and response.content.startswith(b"%PDF"):
            return response.content
        problems.append(f"HTTP {response.status}" if not response.ok else "the file is not a PDF")
    raise FetchError("; ".join(dict.fromkeys(problems)))
