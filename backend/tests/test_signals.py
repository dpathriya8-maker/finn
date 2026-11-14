"""Raw EOD signals: the numbers the app compares against the user's thresholds."""
from datetime import date, timedelta

from app.push.signals import compute_signals
from app.sources.models import Bar


def make_bars(closes, volumes, adj=None):
    start = date(2026, 1, 1)
    return [
        Bar(start + timedelta(days=i), c, c, c, c, v, adj[i] if adj else None)
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


def test_price_move_and_volume_ratio_are_computed_from_the_previous_sessions():
    closes = [100.0] * 21 + [110.0]
    volumes = [1000] * 21 + [3000]
    last = compute_signals(make_bars(closes, volumes))[-1]
    assert last.change_pct == 10.0
    assert last.avg_volume == 1000  # the 20 sessions before the measured one
    assert last.volume_ratio == 3.0
    assert (last.close, last.prev_close, last.volume) == (110.0, 100.0, 3000)


def test_the_measured_day_is_not_part_of_its_own_average():
    # Averaging in today's 5,000 would give 1,190 and a ratio of 4.2, hiding how unusual the day is.
    volumes = [1000] * 20 + [5000]
    last = compute_signals(make_bars([10.0] * 21, volumes))[-1]
    assert last.avg_volume == 1000 and last.volume_ratio == 5.0


def test_without_enough_history_there_is_no_ratio_but_there_is_still_a_move():
    sigs = compute_signals(make_bars([100.0, 95.0, 99.75], [10, 10, 10]), lookback=20)
    assert [s.volume_ratio for s in sigs] == [None, None]
    assert [s.change_pct for s in sigs] == [-5.0, 5.0]


def test_a_stock_split_is_not_reported_as_a_price_move():
    # Raw close halves because of a 2-for-1 split, but the adjusted series is flat.
    bars = make_bars([100.0, 50.0], [10, 10], adj=[50.0, 50.0])
    assert compute_signals(bars)[-1].change_pct == 0.0


def test_a_zero_volume_history_gives_no_ratio_instead_of_dividing_by_zero():
    last = compute_signals(make_bars([10.0] * 21, [0] * 20 + [500]))[-1]
    assert last.volume_ratio is None and last.avg_volume is None


def test_only_the_most_recent_sessions_are_returned_oldest_first():
    sigs = compute_signals(make_bars([float(i + 100) for i in range(40)], [100] * 40), last_n=5)
    assert len(sigs) == 5
    assert [s.day for s in sigs] == sorted(s.day for s in sigs)
    assert sigs[-1].day == date(2026, 1, 1) + timedelta(days=39)


def test_too_few_bars_return_nothing():
    assert compute_signals(make_bars([100.0], [10])) == []
    assert compute_signals([]) == []
