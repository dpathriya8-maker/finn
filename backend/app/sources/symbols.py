"""NSE symbol to BSE scrip code, joined on the ISIN that both exchanges publish."""
from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path
from typing import Any

from app.core.http import FetchError, fetch
from app.sources.bse import HEADERS as BSE_HEADERS
from app.sources.models import Listing

BSE_SCRIPS_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/ListOfScripData/w"
    "?Group=&Scripcode=&industry=&segment=Equity&status=Active"
)
NSE_EQUITIES_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"  # gitignored
TTL_SECONDS = 24 * 3600


def build_index(nse_csv: str, bse_scrips: list[dict[str, Any]]) -> dict[str, Listing]:
    """Map every NSE symbol to its listing, with the BSE scrip code when BSE lists the same ISIN."""
    by_isin = {row["ISIN_NUMBER"]: row for row in bse_scrips if row.get("ISIN_NUMBER")}
    index: dict[str, Listing] = {}
    for raw in csv.DictReader(io.StringIO(nse_csv)):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}  # NSE pads its headers
        symbol, isin = row.get("SYMBOL", ""), row.get("ISIN NUMBER", "")
        if not symbol or not isin:
            continue
        bse = by_isin.get(isin)
        index[symbol] = Listing(
            symbol=symbol,
            name=row.get("NAME OF COMPANY", ""),
            isin=isin,
            bse_code=str(bse["SCRIP_CD"]) if bse else None,
            bse_id=bse.get("scrip_id") if bse else None,
        )
    return index


def _cached_text(name: str, url: str, headers: dict[str, str], *, refresh: bool = False) -> str:
    """Download once a day. If the download fails, fall back to the last copy and say nothing is fresh."""
    path = CACHE_DIR / name
    fresh = path.exists() and time.time() - path.stat().st_mtime < TTL_SECONDS
    if fresh and not refresh:
        return path.read_text(encoding="utf-8")
    try:
        resp = fetch(url, headers=headers, timeout=(10, 60))
        if not resp.ok:
            raise FetchError(f"HTTP {resp.status}")
        text = resp.text()
    except FetchError:
        if path.exists():
            return path.read_text(encoding="utf-8")  # stale beats nothing
        raise
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


_index: dict[str, Listing] | None = None


def load_index(*, refresh: bool = False) -> dict[str, Listing]:
    """Every NSE symbol with its BSE scrip code where BSE has one. BSE refuses some servers (Render gets HTTP 403 from it),
    and then the index is NSE-only: no company has a scrip code, so each is read through NSE's own filings feed."""
    global _index
    if _index is None or refresh:
        nse = _cached_text("nse_equity.csv", NSE_EQUITIES_URL, {"User-Agent": BSE_HEADERS["User-Agent"]}, refresh=refresh)
        try:
            bse = json.loads(_cached_text("bse_scrips.json", BSE_SCRIPS_URL, BSE_HEADERS, refresh=refresh))
        except (FetchError, ValueError):
            bse = []
        _index = build_index(nse, bse)
    return _index


def resolve(symbol: str, *, refresh: bool = False) -> Listing | None:
    """The listing for an NSE symbol, or None if NSE has no such symbol. If NSE's list itself cannot be fetched, the symbol is
    taken as typed (it was validated as a ticker already) and NSE's filings feed decides: a symbol it does not know has no
    filings, which the research then says."""
    name = symbol.strip().upper()
    try:
        return load_index(refresh=refresh).get(name)
    except (FetchError, ValueError):
        return Listing(symbol=name, name=name, isin="", bse_code=None, bse_id=None)
