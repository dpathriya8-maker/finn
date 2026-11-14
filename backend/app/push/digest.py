"""Assemble the windowed digest JSON consumed by the frontend."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.push.classify import classify
from app.push.headline import make_headline
from app.push.priority import score
from app.push.signals import Signal
from app.sources.models import Announcement, Bar, Listing, QuarterFigures

SCHEMA = 1
BODY_LIMIT = 600  # characters of announcement text kept per item


def announcement_item(a: Announcement, *, symbol: str, company: str) -> dict[str, Any]:
    cls = classify(
        source=a.source, category=a.category, subcategory=a.subcategory, subject=a.subject, body=a.body
    )
    scored = score(cls)
    return {
        "id": f"{a.source}:{a.id}",
        "symbol": symbol,
        "company": company,
        "source": a.source,
        "published_at": a.published_at.isoformat(timespec="seconds"),
        "category": scored.category,
        "category_label": scored.label,
        "card_type": scored.card_type,
        "priority": scored.priority,
        "routine": scored.routine,
        "default_alert": scored.default_alert,
        "why": scored.why,
        "headline": make_headline(a.subject, a.body),
        "rule": cls.rule,  # which rule decided, so a classification can be audited
        "subject": a.subject,
        "body": a.body[:BODY_LIMIT],
        "raw_category": a.category,
        "raw_subcategory": a.subcategory,
        "url": a.attachment_url,
        "size_kb": round(a.attachment_bytes / 1024) if a.attachment_bytes else None,
    }


def dedupe_results(items: list[dict[str, Any]], *, within_hours: int = 24) -> list[dict[str, Any]]:
    """A results announcement is usually filed twice on BSE: once as 'Result' and once as the board meeting's
    outcome. Showing both would double-count the most important card, so keep one per company and day,
    preferring the filing the exchange itself labels as results. The kept item records how many it absorbed."""
    window = timedelta(hours=within_hours)
    kept = [i for i in items if i["category"] != "results"]
    by_company: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item["category"] == "results":
            by_company.setdefault(item["symbol"], []).append(item)

    for group in by_company.values():
        group.sort(key=lambda i: i["published_at"])
        cluster: list[dict[str, Any]] = []
        for item in [*group, None]:
            if item is not None and (
                not cluster
                or datetime.fromisoformat(item["published_at"]) - datetime.fromisoformat(cluster[-1]["published_at"]) <= window
            ):
                cluster.append(item)
                continue
            best = next((i for i in cluster if i["raw_category"] in ("Result", "Integrated Filing- Financial")), cluster[0])
            kept.append({**best, "merged": len(cluster) - 1})
            cluster = [item] if item is not None else []
    return sorted(kept, key=lambda i: i["published_at"], reverse=True)


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
