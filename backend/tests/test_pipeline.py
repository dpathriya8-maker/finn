"""The data pipeline: source choice, graceful failure, and the files it writes. No network."""
import json
from datetime import date, datetime, timedelta

import pytest

from app.core.timeutil import IST
from app.sources.models import Announcement, Bar, Listing, PriceHistory, QuarterFigures
from pipeline.run import Sources, load_companies, run

NOW = datetime(2026, 11, 15, 9, 0, tzinfo=IST)
RELIANCE = {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "sector": "Energy", "size_bucket": "large"}
CDSL = {"symbol": "CDSL", "name": "CDSL", "sector": "Markets", "size_bucket": "small"}


def ann(n, hours_ago, source="bse"):
    return Announcement(
        source, f"id{n}", "Co", "500325", "Company Update", "General", f"Subject {n}", "Body " * 200,
        NOW - timedelta(hours=hours_ago), "https://www.bseindia.com/xml-data/corpfiling/AttachLive/x.pdf", 2048,
    )


def history(symbol="RELIANCE.NS", n=30):
    bars = [Bar(date(2026, 10, 1) + timedelta(days=i), 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000 + i) for i in range(n)]
    return PriceHistory("X", symbol, bars)


def make_sources(**overrides):
    base = dict(
        resolve=lambda s: Listing(s, s, "INE000000001", "500325" if s != "CDSL" else None, s if s != "CDSL" else None),
        bse_window=lambda code, start, end: [ann(1, 2), ann(2, 30)],
        nse_window=lambda sym, start, end: [ann(9, 5, "nse")],
        history=lambda s: history(),
        quarters=lambda s: [QuarterFigures(date(2026, 9, 30), 1000.0, 200.0, 150.0, 100.0)],
    )
    base.update(overrides)
    return Sources(**base)


def go(tmp_path, portfolio=(RELIANCE,), **kwargs):
    return run(list(portfolio), out_dir=tmp_path, now=kwargs.pop("now", NOW), pause=0, log=lambda _m: None, **kwargs)


def read(tmp_path, name):
    return json.loads((tmp_path / name).read_text(encoding="utf-8"))


def test_a_normal_run_writes_the_company_file_the_brief_and_the_meta(tmp_path):
    report = go(tmp_path, sources=make_sources())
    assert report.processed == ["RELIANCE"] and report.failures == {}
    rec = read(tmp_path, "RELIANCE.json")
    assert rec["sources"] == {"announcements": "bse", "prices": "RELIANCE.NS", "quarters": "yahoo"}
    assert rec["errors"] == {} and rec["stale"] == {}
    assert len(rec["announcements"]) == 2 and len(rec["prices"]) == 30 and len(rec["signals"]) == 5
    assert rec["announcements"][0]["id"] == "bse:id1" and rec["announcements"][0]["size_kb"] == 2
    assert len(rec["announcements"][0]["body"]) <= 600
    assert rec["listing"]["bse_code"] == "500325"
    brief = read(tmp_path, "brief.json")
    assert [i["id"] for i in brief["items"]] == ["bse:id1", "bse:id2"]  # newest first
    assert brief["signals"][0]["symbol"] == "RELIANCE" and len(brief["signals"][0]["sessions"]) == 5
    meta = read(tmp_path, "meta.json")
    assert meta["companies"] == 1 and meta["announcement_sources"] == {"bse": 1, "nse": 0}
    assert "note" not in meta  # real data is never labelled as the skeleton sample


def test_a_company_bse_does_not_list_goes_to_nse_without_touching_bse(tmp_path):
    def boom(*_a, **_k):
        raise AssertionError("BSE must not be called for an NSE-only company")

    go(tmp_path, portfolio=[CDSL], sources=make_sources(bse_window=boom))
    rec = read(tmp_path, "CDSL.json")
    assert rec["sources"]["announcements"] == "nse" and rec["announcements"][0]["id"] == "nse:id9"
    assert rec["errors"] == {}


def test_when_bse_fails_nse_covers_and_the_failure_is_recorded(tmp_path):
    def down(*_a, **_k):
        raise ConnectionError("BSE unreachable")

    go(tmp_path, sources=make_sources(bse_window=down))
    rec = read(tmp_path, "RELIANCE.json")
    assert rec["sources"]["announcements"] == "nse"
    assert "ConnectionError" in rec["errors"]["announcements_bse"]
    assert rec["stale"] == {}  # data is fresh, just from the other exchange


def test_a_failing_source_keeps_the_last_good_data_and_says_so(tmp_path):
    go(tmp_path, sources=make_sources())  # first run succeeds
    first = read(tmp_path, "RELIANCE.json")

    def down(*_a, **_k):
        raise TimeoutError("took too long")

    later = NOW + timedelta(hours=6)
    go(tmp_path, sources=make_sources(bse_window=down, nse_window=down, history=down, quarters=down), now=later)
    rec = read(tmp_path, "RELIANCE.json")
    assert rec["announcements"] == first["announcements"] and rec["prices"] == first["prices"]
    assert rec["signals"] == first["signals"] and rec["yahoo_quarters"] == first["yahoo_quarters"]
    assert set(rec["stale"]) == {"announcements", "prices", "quarters"}
    assert set(rec["stale"].values()) == {first["generated_at"]}  # when the reused data was produced
    assert rec["generated_at"] != first["generated_at"]
    assert {"announcements", "prices", "quarters"} <= set(rec["errors"])
    assert read(tmp_path, "brief.json")["items"]  # the feed is not blank
    assert read(tmp_path, "meta.json")["with_stale_data"] == ["RELIANCE"]


def test_staleness_keeps_the_original_timestamp_across_repeated_failures(tmp_path):
    go(tmp_path, sources=make_sources())
    first_stamp = read(tmp_path, "RELIANCE.json")["generated_at"]

    def down(*_a, **_k):
        raise TimeoutError("x")

    for hours in (6, 12):
        go(tmp_path, sources=make_sources(bse_window=down, nse_window=down), now=NOW + timedelta(hours=hours))
    assert read(tmp_path, "RELIANCE.json")["stale"]["announcements"] == first_stamp


def test_an_unknown_symbol_is_reported_not_crashed_on(tmp_path):
    report = go(tmp_path, sources=make_sources(resolve=lambda s: None))
    rec = read(tmp_path, "RELIANCE.json")
    assert "not on NSE" in rec["errors"]["listing"] and rec["listing"] is None
    assert rec["sources"]["announcements"] == "nse"  # NSE is keyed by symbol, so it can still be tried
    assert "RELIANCE" in report.failures


def test_a_partial_run_leaves_other_companies_in_the_brief(tmp_path):
    go(tmp_path, portfolio=[RELIANCE, CDSL], sources=make_sources())
    go(tmp_path, portfolio=[RELIANCE, CDSL], only=["cdsl"], sources=make_sources(), now=NOW + timedelta(hours=1))
    brief = read(tmp_path, "brief.json")
    assert {c["symbol"] for c in brief["companies"]} == {"RELIANCE", "CDSL"}
    assert read(tmp_path, "RELIANCE.json")["generated_at"] == NOW.isoformat(timespec="seconds")  # untouched


def test_no_temp_files_are_left_behind(tmp_path):
    go(tmp_path, sources=make_sources())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["RELIANCE.json", "brief.json", "meta.json"]


def test_research_companies_get_their_own_file_but_stay_out_of_the_brief(tmp_path):
    run([RELIANCE], [CDSL], out_dir=tmp_path, now=NOW, sources=make_sources(), pause=0, log=lambda _m: None)
    assert (tmp_path / "CDSL.json").exists()
    assert [c["symbol"] for c in read(tmp_path, "brief.json")["companies"]] == ["RELIANCE"]


def test_the_real_config_loads_18_portfolio_and_4_research_companies():
    portfolio, research = load_companies(include_research=True)
    assert (len(portfolio), len(research)) == (18, 4)
    assert load_companies()[1] == []
