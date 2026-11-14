"""Plain data types shared by the source clients (exchange announcements, prices, listings)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Announcement:
    """One corporate announcement, normalised from either exchange."""

    source: str  # "bse" or "nse"
    id: str
    company: str
    symbol: str  # NSE symbol for NSE rows, BSE scrip code for BSE rows
    category: str  # BSE CATEGORYNAME, or NSE desc
    subcategory: str  # BSE SUBCATNAME; empty for NSE
    subject: str
    body: str
    published_at: datetime  # timezone-aware, IST
    attachment_url: str | None
    attachment_bytes: int | None


@dataclass(frozen=True)
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class PriceHistory:
    symbol: str
    yahoo_symbol: str  # e.g. RELIANCE.NS, or RELIANCE.BO when NSE had too little data
    bars: list[Bar]  # oldest first


@dataclass(frozen=True)
class QuarterFigures:
    """Quarterly figures from yfinance, in Rs crore. Used only to cross-check the results filing."""

    period_end: date
    revenue_cr: float | None
    ebitda_cr: float | None
    pbt_cr: float | None
    net_income_cr: float | None


@dataclass(frozen=True)
class Listing:
    """Where a ticker lives. `bse_code` is None for companies BSE does not list (for example CDSL)."""

    symbol: str
    name: str
    isin: str
    bse_code: str | None
    bse_id: str | None
