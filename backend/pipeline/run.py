"""Precompute everything into frontend/public/data/*.json (run daily or on demand).

    python -m pipeline.run                      # the 18 portfolio companies
    python -m pipeline.run --symbols RELIANCE   # just these (the brief is rebuilt from all existing files)
    python -m pipeline.run --research           # also the research companies

Raw metrics only: price move and volume ratio are stored as numbers, and the app applies the user's
thresholds. If a source fails, the last good data for that part is kept and flagged as stale.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from app.core.cache import Cache, default_cache
from app.core.settings import REPO_ROOT
from app.core.timeutil import now_ist
from app.push import cards, digest
from app.push.signals import compute_signals
from app.sources import bse, documents, nse, prices, symbols
from app.sources.models import Announcement, Listing, PriceHistory, QuarterFigures

DEFAULT_OUT = REPO_ROOT / "frontend" / "public" / "data"
SESSIONS_KEPT = 30  # price sessions kept per company: the Brief and Alerts use the last few, the sparklines draw all
ITEM_DAYS = 14  # how far back announcements are kept; the app offers windows up to 7 days
PAUSE_BETWEEN_COMPANIES_S = 0.3


@dataclass
class Sources:
    """The data sources, injectable so tests can fake them."""

    resolve: Callable[[str], Listing | None] = symbols.resolve
    bse_window: Callable[..., list[Announcement]] = bse.fetch_window
    nse_window: Callable[..., list[Announcement]] = nse.fetch_announcements
    history: Callable[[str], PriceHistory] = prices.fetch_history
    quarters: Callable[[str], list[QuarterFigures]] = prices.quarterly_financials
    pdf: Callable[[str], bytes] = documents.fetch_pdf
    cache: Cache | None = None  # what was read from each filing; None keeps nothing between runs (the CLI passes the on-disk one)


@dataclass
class RunReport:
    processed: list[str] = field(default_factory=list)
    failures: dict[str, dict[str, str]] = field(default_factory=dict)


def load_companies(include_research: bool = False) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    def read(name: str) -> list[dict[str, str]]:
        return json.loads((REPO_ROOT / "config" / name).read_text(encoding="utf-8"))["companies"]

    return read("portfolio.json"), (read("research.json") if include_research else [])


def write_json(path: Path, data: Any, *, indent: int | None = None) -> None:
    """Write via a temp file so a crash never leaves a half-written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def app_config() -> dict[str, Any]:
    """The settings defaults and the category list, published as static JSON because the deployed
    frontend cannot read files outside its own folder. config/ stays the single source of truth."""
    defaults = json.loads((REPO_ROOT / "config" / "defaults.json").read_text(encoding="utf-8"))
    categories = json.loads((REPO_ROOT / "config" / "categories.json").read_text(encoding="utf-8"))["categories"]
    keep = ("id", "label", "why", "weight", "is_routine", "default_alert", "card_type")
    return {"schema": digest.SCHEMA, "defaults": defaults, "categories": [{k: c[k] for k in keep} for c in categories]}


def _read_previous(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def process_company(
    company: dict[str, str], *, sources: Sources, start: date, now: datetime, previous: dict[str, Any]
) -> dict[str, Any]:
    symbol, today = company["symbol"], now.date()
    errors: dict[str, str] = {}
    stale: dict[str, str] = {}

    def failed(part: str, exc: Exception) -> None:
        errors[part] = f"{type(exc).__name__}: {str(exc)[:200]}"

    def reuse(part: str) -> None:
        stale[part] = previous.get("stale", {}).get(part) or previous.get("generated_at", "unknown")

    listing: Listing | None = None
    try:
        listing = sources.resolve(symbol)
        if listing is None:
            errors["listing"] = f"{symbol} is not on NSE's equity list"
    except Exception as exc:
        failed("listing", exc)

    # Announcements: BSE when the company has a scrip code (or when NSE has no listing for it), else NSE,
    # and the other exchange as a fallback if the first one fails.
    ann_items, ann_source = None, None
    attempts: list[tuple[str, Callable[[], list[Announcement]]]] = []
    if listing and listing.bse_code:
        attempts.append(("bse", lambda: sources.bse_window(listing.bse_code, start, today)))
    attempts.append(("nse", lambda: sources.nse_window(symbol, start, today)))
    for name, fetch in attempts:
        try:
            found = fetch()
            ann_items = digest.dedupe_results(
                [digest.announcement_item(a, symbol=symbol, company=company["name"]) for a in found]
            )
            ann_source = name
            break
        except Exception as exc:
            failed("announcements" if name == attempts[-1][0] else f"announcements_{name}", exc)
    announcements_fresh = ann_items is not None
    if ann_items is None:
        ann_items, ann_source = previous.get("announcements", []), previous.get("sources", {}).get("announcements")
        reuse("announcements")

    price_rows, price_symbol, signal_rows = None, None, None
    try:
        history = sources.history(symbol)
        price_rows = [digest.bar_row(b) for b in history.bars]
        price_symbol = history.yahoo_symbol
        signal_rows = [digest.signal_dict(s) for s in compute_signals(history.bars, last_n=SESSIONS_KEPT)]
    except Exception as exc:
        failed("prices", exc)
        price_rows, price_symbol, signal_rows = (
            previous.get("prices", []),
            previous.get("sources", {}).get("prices"),
            previous.get("signals", []),
        )
        reuse("prices")

    try:
        quarter_rows = [digest.quarter_dict(q) for q in sources.quarters(symbol)]
    except Exception as exc:
        failed("quarters", exc)
        quarter_rows = previous.get("yahoo_quarters", [])
        reuse("quarters")

    # The cards that look inside a filing: the figures of results, the people in a management change. Items kept from
    # the last run (the source failed) already carry theirs.
    card_counts: dict[str, dict[str, int]] = {}
    if announcements_fresh:
        earlier = {i["id"]: i["card"] for i in previous.get("announcements", []) if i.get("card")}
        pdf = cards.PdfOnce(sources.pdf)  # one download per file, even when two announcements share it
        for kind, attach, extra in (
            ("results", cards.attach_results_cards, {"yahoo": quarter_rows}),
            ("management", cards.attach_management_cards, {}),
        ):
            try:
                card_counts[kind] = attach(ann_items, pdf=pdf, cache=sources.cache, previous=earlier, **extra)
            except Exception as exc:  # a card is an extra: it must never take the company's other data down
                failed(f"cards_{kind}", exc)

    return digest.company_record(
        company=company,
        listing=listing,
        now=now,
        announcements=ann_items,
        announcements_source=ann_source,
        prices=price_rows,
        price_symbol=price_symbol,
        signals=signal_rows,
        quarters=quarter_rows,
        cards=card_counts,
        errors=errors,
        stale=stale,
    )


def _cards_summary(counts: dict[str, dict[str, int]]) -> str:
    parts = []
    for kind, numbers in counts.items():
        shown = ", ".join(f"{numbers[k]} {k}" for k in ("ok", "partial", "failed", "reused", "cached") if numbers.get(k))
        if shown:
            parts.append(f"{kind} {shown}")
    return "; ".join(parts)


def run(
    portfolio: list[dict[str, str]],
    research: list[dict[str, str]] | None = None,
    *,
    only: list[str] | None = None,
    out_dir: Path = DEFAULT_OUT,
    days: int = ITEM_DAYS,
    now: datetime | None = None,
    sources: Sources | None = None,
    pause: float = PAUSE_BETWEEN_COMPANIES_S,
    log: Callable[[str], None] = print,
) -> RunReport:
    now = now or now_ist()
    sources = sources or Sources()
    start = now.date() - timedelta(days=days)
    report = RunReport()
    wanted = {s.upper() for s in only} if only else None

    for company in [*portfolio, *(research or [])]:
        symbol = company["symbol"]
        if wanted and symbol not in wanted:
            continue
        path = out_dir / f"{symbol}.json"
        record = process_company(company, sources=sources, start=start, now=now, previous=_read_previous(path))
        write_json(path, record)
        report.processed.append(symbol)
        if record["errors"]:
            report.failures[symbol] = record["errors"]
        log(
            f"{symbol:11s} {record['sources']['announcements'] or '-':3s} {len(record['announcements']):3d} filings | "
            f"{record['sources']['prices'] or '-':14s} {len(record['prices']):3d} bars"
            + (f" | cards: {_cards_summary(record['cards'])}" if _cards_summary(record["cards"]) else "")
            + (f" | PROBLEMS: {record['errors']}" if record["errors"] else "")
            + (f" | stale: {sorted(record['stale'])}" if record["stale"] else "")
        )
        time.sleep(pause)

    # The brief is always rebuilt from every portfolio file on disk, so a partial run keeps the rest.
    records = [r for c in portfolio if (r := _read_previous(out_dir / f"{c['symbol']}.json"))]
    write_json(out_dir / "brief.json", digest.brief(records, now=now, item_days=days))
    write_json(out_dir / "config.json", app_config(), indent=1)
    write_json(
        out_dir / "meta.json",
        {
            "schema": digest.SCHEMA,
            "generated_at": now.isoformat(timespec="seconds"),
            "item_days": days,
            "companies": len(records),
            "announcement_sources": {
                s: sum(1 for r in records if r["sources"]["announcements"] == s) for s in ("bse", "nse")
            },
            "cards": {
                kind: {k: sum(r.get("cards", {}).get(kind, {}).get(k, 0) for r in records) for k in ("ok", "partial", "failed")}
                for kind in ("results", "management")
            },
            "with_problems": sorted(r["symbol"] for r in records if r["errors"]),
            "with_stale_data": sorted(r["symbol"] for r in records if r["stale"]),
        },
        indent=2,
    )
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Precompute the static JSON the app reads.")
    parser.add_argument("--symbols", nargs="*", help="only these NSE symbols")
    parser.add_argument("--research", action="store_true", help="also process the research companies")
    parser.add_argument("--days", type=int, default=ITEM_DAYS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    portfolio, research = load_companies(args.research)
    report = run(portfolio, research, only=args.symbols, out_dir=args.out, days=args.days, sources=Sources(cache=default_cache()))
    print(f"\n{len(report.processed)} companies processed, {len(report.failures)} with problems -> {args.out}")
    return 0 if report.processed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
