"""Assemble the windowed digest JSON consumed by the frontend."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.push.signals import Signal
from app.sources.models import Announcement, Bar, Listing, QuarterFigures

SCHEMA = 1
BODY_LIMIT = 600  # characters of announcement text kept per item


def announcement_item(a: Announcement, *, symbol: str, company: str) -> dict[str, Any]:
    return {
        "id": f"{a.source}:{a.id}",
        "symbol": symbol,
        "company": company,
        "source": a.source,
        "published_at": a.published_at.isoformat(timespec="seconds"),
        "subject": a.subject,
        "body": a.body[:BODY_LIMIT],
        "raw_category": a.category,
        "raw_subcategory": a.subcategory,
        "url": a.attachment_url,
        "size_kb": round(a.attachment_bytes / 1024) if a.attachment_bytes else None,
    }


def signal_dict(s: Signal) -> dict[str, Any]:
    return {
        "day": s.day.isoformat(),
        "close": s.close,
        "prev_close": s.prev_close,
        "change_pct": s.change_pct,
        "volume": s.volume,
        "avg_volume": s.avg_volume,
        "volume_ratio": s.volume_ratio,
    }


def bar_row(b: Bar) -> list[Any]:
    return [b.day.isoformat(), round(b.open, 2), round(b.high, 2), round(b.low, 2), round(b.close, 2), b.volume]


def quarter_dict(q: QuarterFigures) -> dict[str, Any]:
    return {
        "period_end": q.period_end.isoformat(),
        "revenue_cr": q.revenue_cr,
        "ebitda_cr": q.ebitda_cr,
        "pbt_cr": q.pbt_cr,
        "net_income_cr": q.net_income_cr,
    }


def listing_dict(listing: Listing | None) -> dict[str, Any] | None:
    if listing is None:
        return None
    return {"isin": listing.isin, "bse_code": listing.bse_code, "bse_id": listing.bse_id, "nse_symbol": listing.symbol}


def company_record(
    *,
    company: dict[str, str],
    listing: Listing | None,
    now: datetime,
    announcements: list[dict[str, Any]],
    announcements_source: str | None,
    prices: list[list[Any]],
    price_symbol: str | None,
    signals: list[dict[str, Any]],
    quarters: list[dict[str, Any]],
    errors: dict[str, str],
    stale: dict[str, str],
) -> dict[str, Any]:
    """Everything the app knows about one company. A part that failed this run keeps its last good data
    and says so in `stale` (part -> when that data was produced); `errors` says why it failed."""
    return {
        "schema": SCHEMA,
        "symbol": company["symbol"],
        "name": company["name"],
        "sector": company["sector"],
        "size_bucket": company["size_bucket"],
        "listing": listing_dict(listing),
        "generated_at": now.isoformat(timespec="seconds"),
        "sources": {"announcements": announcements_source, "prices": price_symbol, "quarters": "yahoo" if quarters else None},
        "errors": errors,
        "stale": stale,
        "prices": prices,
        "signals": signals,
        "announcements": announcements,
        "yahoo_quarters": quarters,
    }


def brief(records: list[dict[str, Any]], *, now: datetime, item_days: int) -> dict[str, Any]:
    """The feed: every announcement of every portfolio company, newest first, plus each company's recent
    EOD signals. The app picks the window and applies the thresholds."""
    items = sorted(
        (item for r in records for item in r["announcements"]), key=lambda i: i["published_at"], reverse=True
    )
    return {
        "schema": SCHEMA,
        "generated_at": now.isoformat(timespec="seconds"),
        "item_days": item_days,
        "companies": [
            {
                "symbol": r["symbol"],
                "name": r["name"],
                "sector": r["sector"],
                "size_bucket": r["size_bucket"],
                "stale": r["stale"],
                "errors": r["errors"],
            }
            for r in records
        ],
        "items": items,
        "signals": [{"symbol": r["symbol"], "sessions": r["signals"]} for r in records],
    }
