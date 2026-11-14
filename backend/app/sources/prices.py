"""EOD price and volume via yfinance (.NS, fallback .BO), and quarterly figures for cross-checks."""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.sources.models import Bar, PriceHistory, QuarterFigures

MIN_BARS = 5  # fewer than this from .NS and we try .BO (BSE-only symbols, or a Yahoo gap)
CRORE = 1e7


class NoPriceData(Exception):
    """Yahoo returned nothing usable for either exchange."""


def _bars(frame: Any) -> list[Bar]:
    bars = []
    for ts, row in frame.iterrows():
        if any(math.isnan(float(row[c])) for c in ("Open", "High", "Low", "Close")):
            continue
        adj = float(row["Adj Close"]) if "Adj Close" in row and not math.isnan(float(row["Adj Close"])) else None
        bars.append(
            Bar(
                day=ts.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]) if not math.isnan(float(row["Volume"])) else 0,
                adj_close=adj,
            )
        )
    return bars


def fetch_history(symbol: str, *, period: str = "3mo") -> PriceHistory:
    """Daily bars, oldest first. Raw (not split-adjusted) prices, because alerts compare to the real close."""
    import yfinance as yf  # heavy import (pandas); keep it out of app start-up

    best: PriceHistory | None = None
    for suffix in (".NS", ".BO"):
        yahoo_symbol = symbol + suffix
        try:
            frame = yf.Ticker(yahoo_symbol).history(period=period, interval="1d", auto_adjust=False)
        except Exception:  # yfinance raises many things; a failed exchange just means "try the next"
            continue
        bars = _bars(frame)
        if len(bars) >= MIN_BARS:
            return PriceHistory(symbol, yahoo_symbol, bars)
        if bars and (best is None or len(bars) > len(best.bars)):
            best = PriceHistory(symbol, yahoo_symbol, bars)
    if best is None:
        raise NoPriceData(f"no price data for {symbol} on .NS or .BO")
    return best


def _cr(frame: Any, label: str, column: Any) -> float | None:
    if label not in frame.index:
        return None
    value = frame.loc[label, column]
    return None if value is None or math.isnan(float(value)) else round(float(value) / CRORE, 2)


def quarterly_financials(symbol: str) -> list[QuarterFigures]:
    """Up to five recent quarters, newest first, in Rs crore. Quarters can be missing (Yahoo skips some),
    and EBITDA does not exist for lenders, so every figure may be None."""
    import yfinance as yf

    frame = yf.Ticker(symbol + ".NS").quarterly_income_stmt
    if frame is None or frame.empty:
        return []
    out = [
        QuarterFigures(
            period_end=col.date() if hasattr(col, "date") else date.fromisoformat(str(col)[:10]),
            revenue_cr=_cr(frame, "Total Revenue", col),
            ebitda_cr=_cr(frame, "EBITDA", col),
            pbt_cr=_cr(frame, "Pretax Income", col),
            net_income_cr=_cr(frame, "Net Income", col),
        )
        for col in frame.columns
    ]
    return sorted(out, key=lambda q: q.period_end, reverse=True)
