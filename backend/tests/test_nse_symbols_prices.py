"""NSE client, the NSE-to-BSE symbol join, and the yfinance wrappers (no network)."""
import json
import sys
import types
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.core.http import Fetched
from app.core.http import FetchError
from app.sources import nse, prices, symbols

FIXTURES = Path(__file__).parent / "fixtures"
NSE_ROWS = json.loads((FIXTURES / "nse_announcements.json").read_text(encoding="utf-8"))


# ---------- NSE ----------
def test_nse_row_is_parsed():
    a = nse.parse_row(NSE_ROWS[0])
    assert a.source == "nse" and a.symbol == "CDSL"
    assert a.company == "Central Depository Services (India) Limited"
    assert a.category == a.subject  # NSE has one description field, not category plus subcategory
    assert a.published_at.utcoffset() == timedelta(hours=5, minutes=30)
    assert a.attachment_url and a.attachment_url.startswith("https://")
    assert a.attachment_bytes and a.attachment_bytes > 1000


@pytest.mark.parametrize("text, expected", [("306.78 KB", 314_142), ("2 MB", 2_097_152), ("512", 512), ("", None), ("n/a", None)])
def test_nse_file_sizes(text, expected):
    assert nse.parse_size(text) == expected


def test_nse_rejects_symbols_that_are_not_valid_tickers():
    with pytest.raises(ValueError):
        nse.fetch_announcements("RELIANCE; DROP", date(2026, 11, 1), date(2026, 11, 2))


def test_nse_visits_the_home_page_first_and_formats_dates(monkeypatch):
    calls = []

    def fake_fetch(url, **kwargs):
        calls.append((url, kwargs.get("params")))
        body = b"<html>" if url == nse.HOME else json.dumps(NSE_ROWS).encode()
        return Fetched(url, 200, body)

    monkeypatch.setattr(nse, "fetch", fake_fetch)
    got = nse.fetch_announcements("M&M", date(2026, 8, 17), date(2026, 11, 15))
    assert calls[0][0] == nse.HOME  # cookies come from the home page
    assert calls[1][1] == {"index": "equities", "symbol": "M&M", "from_date": "17-08-2026", "to_date": "15-11-2026"}
    assert [a.published_at for a in got] == sorted((a.published_at for a in got), reverse=True)


def test_nse_retries_once_with_a_fresh_session(monkeypatch):
    calls = []
    answers = iter([403, 200])  # the API answer for the first and second attempt

    def fake_fetch(url, *, session=None, **kwargs):
        calls.append((url, session))
        if url == nse.HOME:
            return Fetched(url, 200, b"<html>")
        return Fetched(url, next(answers), json.dumps(NSE_ROWS).encode())

    monkeypatch.setattr(nse, "fetch", fake_fetch)
    got = nse.fetch_announcements("CDSL", date(2026, 8, 17), date(2026, 11, 15))
    assert len(got) == 3 and len(calls) == 4
    assert calls[0][1] is calls[1][1] and calls[2][1] is calls[3][1]  # one session per attempt
    assert calls[0][1] is not calls[2][1]  # and a new one for the retry


def test_nse_gives_up_after_the_second_failure(monkeypatch):
    monkeypatch.setattr(nse, "fetch", lambda url, **kw: Fetched(url, 403 if url != nse.HOME else 200, b"denied"))
    with pytest.raises(nse.FetchError, match="HTTP 403"):
        nse.fetch_announcements("CDSL", date(2026, 8, 17), date(2026, 11, 15))


# ---------- symbol mapping ----------
@pytest.fixture
def index():
    csv_text = (FIXTURES / "nse_equity_sample.csv").read_text(encoding="utf-8")
    scrips = json.loads((FIXTURES / "bse_scrips_sample.json").read_text(encoding="utf-8"))
    return symbols.build_index(csv_text, scrips)


def test_join_on_isin_finds_the_bse_scrip_code(index):
    reliance = index["RELIANCE"]
    assert (reliance.bse_code, reliance.bse_id, reliance.isin) == ("500325", "RELIANCE", "INE002A01018")
    assert index["M&M"].bse_code == "500520"  # symbols with punctuation work


def test_a_company_bse_does_not_list_has_no_bse_code_instead_of_a_wrong_one(index):
    cdsl = index["CDSL"]
    assert cdsl.bse_code is None and cdsl.isin == "INE736A01011"
    # BSE does have a similarly named scrip (ICDS Ltd, 511194); matching by name would have picked it.
    assert "511194" not in {listing.bse_code for listing in index.values()}


def test_resolve_cleans_the_input_and_returns_none_for_unknown_symbols(index, monkeypatch):
    monkeypatch.setattr(symbols, "load_index", lambda refresh=False: index)
    assert symbols.resolve("  reliance ").bse_code == "500325"
    assert symbols.resolve("NOSUCHCO") is None


# ---------- yfinance wrappers ----------
def test_bars_skip_rows_with_missing_prices():
    frame = pd.DataFrame(
        {"Open": [10.0, float("nan")], "High": [11.0, float("nan")], "Low": [9.0, float("nan")],
         "Close": [10.5, float("nan")], "Volume": [1000, float("nan")]},
        index=pd.to_datetime(["2026-11-12", "2026-11-13"]),
    )
    bars = prices._bars(frame)
    assert [(b.day, b.close, b.volume) for b in bars] == [(date(2026, 11, 12), 10.5, 1000)]


def test_quarterly_figures_are_converted_to_crore_and_missing_rows_become_none(monkeypatch):
    cols = pd.to_datetime(["2026-06-30", "2026-09-30"])
    stmt = pd.DataFrame({cols[0]: [1.0e10, 2.0e9], cols[1]: [1.2e10, 2.5e9]}, index=["Total Revenue", "Pretax Income"])
    fake = types.SimpleNamespace(Ticker=lambda _s: types.SimpleNamespace(quarterly_income_stmt=stmt))
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    quarters = prices.quarterly_financials("RELIANCE")
    assert [q.period_end for q in quarters] == [date(2026, 9, 30), date(2026, 6, 30)]  # newest first
    assert quarters[0].revenue_cr == 1200.0 and quarters[0].pbt_cr == 250.0
    assert quarters[0].ebitda_cr is None  # lenders have no EBITDA row



# ---------------------------------------------------------------------------------------------- a server BSE refuses (Render)
def test_when_bse_refuses_the_server_the_index_is_nse_only_so_every_company_is_read_through_nse(monkeypatch):
    csv_text = "SYMBOL,NAME OF COMPANY, SERIES, ISIN NUMBER\nTITAN,Titan Company Limited,EQ,INE280A01028\nRELIANCE,Reliance Industries Limited,EQ,INE002A01018\n"

    def fake(name, url, headers, *, refresh=False):
        if name == "bse_scrips.json":
            raise FetchError("HTTP 403")
        return csv_text

    monkeypatch.setattr(symbols, "_cached_text", fake)
    monkeypatch.setattr(symbols, "_index", None)
    found = symbols.resolve("titan")
    assert found.symbol == "TITAN" and found.bse_code is None and found.isin == "INE280A01028"
    assert symbols.resolve("NOSUCHCO") is None  # NSE's list is still the judge of what exists
    monkeypatch.setattr(symbols, "_index", None)


def test_when_nses_own_list_cannot_be_fetched_the_symbol_is_taken_as_typed_and_the_filings_feed_decides(monkeypatch):
    def fake(name, url, headers, *, refresh=False):
        raise FetchError("HTTP 403")

    monkeypatch.setattr(symbols, "_cached_text", fake)
    monkeypatch.setattr(symbols, "_index", None)
    listing = symbols.resolve(" titan ")
    assert (listing.symbol, listing.name, listing.bse_code) == ("TITAN", "TITAN", None)
