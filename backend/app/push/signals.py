"""Raw EOD signals: volume ratio vs 20-day average and percent price move (thresholds are applied client-side)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.sources.models import Bar


@dataclass(frozen=True)
class Signal:
    day: date
    close: float
    prev_close: float
    change_pct: float  # close to close, from adjusted prices so a split or bonus is not a "move"
    volume: int
    avg_volume: float | None  # mean volume of the `lookback` sessions before this one
    volume_ratio: float | None  # volume divided by avg_volume


def _change_pct(prev: Bar, cur: Bar) -> float:
    if prev.adj_close and cur.adj_close:
        return (cur.adj_close / prev.adj_close - 1) * 100
    return (cur.close / prev.close - 1) * 100


def compute_signals(bars: list[Bar], *, lookback: int = 20, last_n: int = 5) -> list[Signal]:
    """Signals for the most recent `last_n` sessions, oldest first.

    The pipeline stores these raw numbers and the app applies the user's thresholds, so changing a
    threshold needs no recompute. The volume average excludes the session being measured. It is None when
    there are fewer than `lookback` earlier sessions or the average is zero.
    """
    out: list[Signal] = []
    for i in range(1, len(bars)):
        prev, cur = bars[i - 1], bars[i]
        window = bars[max(0, i - lookback) : i]
        avg = sum(b.volume for b in window) / len(window) if len(window) == lookback else None
        out.append(
            Signal(
                day=cur.day,
                close=round(cur.close, 2),
                prev_close=round(prev.close, 2),
                change_pct=round(_change_pct(prev, cur), 2),
                volume=cur.volume,
                avg_volume=round(avg) if avg else None,
                volume_ratio=round(cur.volume / avg, 2) if avg else None,
            )
        )
    return out[-last_n:]
