"""The data pipeline: source choice, graceful failure, and the files it writes. No network."""
import json
from datetime import date, datetime, timedelta

import pytest

from app.core.cache import Cache
from app.core.timeutil import IST
from app.sources.models import Announcement, Bar, Listing, PriceHistory, QuarterFigures
from pipeline.run import Sources, load_companies, run
from tests.pdfs import make_pdf

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


def no_network(url):
    raise AssertionError(f"this test must not download {url}")


def make_sources(**overrides):
    base = dict(
        pdf=no_network,
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
    assert sorted(p.name for p in tmp_path.iterdir()) == ["RELIANCE.json", "brief.json", "config.json", "meta.json"]


def test_the_app_config_is_published_from_the_config_folder(tmp_path):
    go(tmp_path, sources=make_sources())
    config = read(tmp_path, "config.json")
    assert config["defaults"] == {"window_hours": 24, "volume_multiple": 2.0, "price_move_pct": 5.0, "volume_lookback_days": 20}
    assert len(config["categories"]) == 17
    assert set(config["categories"][0]) == {"id", "label", "why", "weight", "is_routine", "default_alert", "card_type"}


def test_research_companies_get_their_own_file_but_stay_out_of_the_brief(tmp_path):
    run([RELIANCE], [CDSL], out_dir=tmp_path, now=NOW, sources=make_sources(), pause=0, log=lambda _m: None)
    assert (tmp_path / "CDSL.json").exists()
    assert [c["symbol"] for c in read(tmp_path, "brief.json")["companies"]] == ["RELIANCE"]


def test_the_real_config_loads_18_portfolio_and_4_research_companies():
    portfolio, research = load_companies(include_research=True)
    assert (len(portfolio), len(research)) == (18, 4)
    assert load_companies()[1] == []


# ---------------------------------------------------------------------------------------------- results cards
RESULT_URL = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/results.pdf"
MATCHING_YAHOO = lambda s: [QuarterFigures(date(2026, 9, 30), 1000.0, 300.0, 200.0, 150.0)]  # agrees with the synthetic filing


def results_ann(hours_ago=3):
    return Announcement(
        "bse", "res1", "Co", "500325", "Result", "Financial Results", "Results for the quarter ended 30 September 2026", "",
        NOW - timedelta(hours=hours_ago), RESULT_URL, 900_000,
    )


def downloader(content):
    calls = []

    def pdf(url):
        calls.append(url)
        if isinstance(content, Exception):
            raise content
        return content

    pdf.calls = calls
    return pdf


def with_results(**overrides):
    return make_sources(bse_window=lambda c, s, e: [results_ann(), ann(1, 30)], quarters=MATCHING_YAHOO, **overrides)


def test_a_results_filing_gets_its_figures_card_and_the_card_reaches_the_brief(tmp_path):
    pdf = downloader(make_pdf())
    report = go(tmp_path, sources=with_results(pdf=pdf, cache=Cache(":memory:")))
    assert report.failures == {} and pdf.calls == [RESULT_URL]  # the one results filing was downloaded; the other filing was not
    rec = read(tmp_path, "RELIANCE.json")
    results = next(i for i in rec["announcements"] if i["category"] == "results")
    assert results["card"]["status"] == "ok" and results["card"]["period"]["label"] == "Q2 FY27"
    assert results["card"]["check"]["status"] == "ok"
    assert results["headline"] == "Q2 FY27 results: profit up 43% from a year ago; revenue up 25%"
    assert "card" not in next(i for i in rec["announcements"] if i["category"] != "results")
    assert rec["cards"]["results"] == {"ok": 1, "partial": 0, "failed": 0, "cached": 0, "reused": 0}
    assert next(i for i in read(tmp_path, "brief.json")["items"] if i["id"] == results["id"])["card"] == results["card"]
    assert read(tmp_path, "meta.json")["cards"] == {"results": {"ok": 1, "partial": 0, "failed": 0}, "management": {"ok": 0, "partial": 0, "failed": 0}}


def test_the_second_run_does_not_download_the_filing_again(tmp_path):
    pdf, cache = downloader(make_pdf()), Cache(":memory:")
    go(tmp_path, sources=with_results(pdf=pdf, cache=cache))
    go(tmp_path, sources=with_results(pdf=pdf, cache=cache), now=NOW + timedelta(hours=6))
    assert len(pdf.calls) == 1
    assert read(tmp_path, "RELIANCE.json")["cards"]["results"]["cached"] == 1


def test_a_filing_that_cannot_be_downloaded_costs_only_its_card(tmp_path):
    report = go(tmp_path, sources=with_results(pdf=downloader(ConnectionError("reset"))))
    rec = read(tmp_path, "RELIANCE.json")
    assert report.failures == {} and rec["errors"] == {}  # the company's data is fine
    results = next(i for i in rec["announcements"] if i["category"] == "results")
    assert results["card"]["status"] == "failed" and "could not be downloaded" in results["card"]["reason"]
    assert len(rec["announcements"]) == 2 and rec["cards"]["results"]["failed"] == 1


def test_a_bug_in_cards_is_contained_and_reported(tmp_path, monkeypatch):
    from app.push import cards

    def boom(*_a, **_k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(cards, "attach_results_cards", boom)
    go(tmp_path, sources=with_results(pdf=downloader(make_pdf())))
    rec = read(tmp_path, "RELIANCE.json")
    assert "RuntimeError" in rec["errors"]["cards_results"] and len(rec["announcements"]) == 2  # filings still published, without cards


def test_filings_kept_from_the_last_run_keep_their_card_and_are_not_ranked_a_second_time(tmp_path):
    weaker = make_pdf(fiddle=lambda t: t["Profit after tax"].__setitem__(0, 80.0))
    go(tmp_path, sources=with_results(pdf=downloader(weaker)))
    first = next(i for i in read(tmp_path, "RELIANCE.json")["announcements"] if i["category"] == "results")
    assert first["priority"] == 95  # 88 plus the weaker-numbers bump

    down = lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("x"))
    go(tmp_path, sources=make_sources(bse_window=down, nse_window=down, pdf=no_network), now=NOW + timedelta(hours=6))
    later = next(i for i in read(tmp_path, "RELIANCE.json")["announcements"] if i["category"] == "results")
    assert later == first  # the same filing, the same card, the same rank


# ---------------------------------------------------------------------------------------------- management cards
MGMT_URL = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/mgmt.pdf"


def management_ann(hours_ago=5):
    return Announcement(
        "bse", "mgmt1", "Co", "500325", "Company Update", "Change in Management", "Announcement under Regulation 30 (LODR)-Change in Management",
        "As per annexure enclosed", NOW - timedelta(hours=hours_ago), MGMT_URL, 700_000,
    )


def appointment_pdf():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(["The Board approved the appointment of Ms. Priya Nair (DIN: 01234567) as Chief Financial Officer", "with effect from 1st December 2026."]):
        page.insert_text((60, 72 + 16 * i), line, fontsize=10)
    return doc.tobytes()


def test_a_management_filing_gets_its_card_and_a_results_filing_in_the_same_file_shares_the_download(tmp_path):
    # One board-outcome letter filed twice (as results and as a management change) is one file: downloaded once.
    both = Announcement("bse", "res2", "Co", "500325", "Result", "Financial Results", "Results for the quarter ended 30 September 2026", "", NOW - timedelta(hours=4), MGMT_URL, 900_000)
    pdf = downloader(appointment_pdf())
    go(tmp_path, sources=make_sources(bse_window=lambda c, s, e: [management_ann(), both], quarters=MATCHING_YAHOO, pdf=pdf))
    rec = read(tmp_path, "RELIANCE.json")
    mgmt = next(i for i in rec["announcements"] if i["category"] == "management_change")
    assert mgmt["card"]["type"] == "management" and mgmt["card"]["people"][0]["name"] == "Ms. Priya Nair"
    assert mgmt["headline"] == "Ms. Priya Nair appointed as Chief Financial Officer, from 1 Dec"
    assert pdf.calls == [MGMT_URL]  # not two downloads of the same file
    assert rec["cards"]["management"]["ok"] == 1
    assert read(tmp_path, "meta.json")["cards"]["management"]["ok"] == 1
