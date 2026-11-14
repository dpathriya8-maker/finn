"""BSE client: parsing real response rows, pagination and the 365-day chunking."""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.core.http import Fetched, FetchError
from app.sources import bse

FIXTURES = Path(__file__).parent / "fixtures"
ROWS = json.loads((FIXTURES / "bse_announcements.json").read_text(encoding="utf-8"))["Table"]
RESULTS, TRANSCRIPT, BAJAJ_TRANSCRIPT, PREFIXED = (bse.parse_row(r) for r in ROWS)


def test_results_row_is_parsed():
    assert RESULTS.source == "bse"
    assert RESULTS.company == "Reliance Industries Ltd"
    assert RESULTS.symbol == "500325"
    assert (RESULTS.category, RESULTS.subcategory) == ("Result", "Financial Results")
    assert RESULTS.published_at.utcoffset() == timedelta(hours=5, minutes=30)
    assert RESULTS.attachment_url.startswith("https://www.bseindia.com/xml-data/corpfiling/AttachLive/")
    assert RESULTS.attachment_url.endswith(".pdf")
    assert RESULTS.attachment_bytes and RESULTS.attachment_bytes > 1_000_000


def test_company_and_scrip_prefix_is_removed_from_the_subject():
    assert PREFIXED.subject == "Outcome Of Board Meeting"
    assert bse.clean_subject("Religare Enterprises Ltd - 532915 - Grant Of Stock Options") == "Grant Of Stock Options"
    # a subject without the prefix is left alone, including dashes inside it
    assert bse.clean_subject("Announcement under Regulation 30 (LODR)-Credit Rating") == (
        "Announcement under Regulation 30 (LODR)-Credit Rating"
    )


def test_transcripts_are_found_by_subcategory_or_by_text():
    assert bse.is_transcript(TRANSCRIPT)  # filed as 'Earnings Call Transcript'
    assert bse.is_transcript(BAJAJ_TRANSCRIPT)  # filed as 'Analyst / Investor Meet'; the body says transcript
    assert not bse.is_transcript(RESULTS)
    assert not bse.is_transcript(PREFIXED)


def test_results_are_found_by_category():
    assert bse.is_results(RESULTS)
    assert not bse.is_results(TRANSCRIPT)


def _page(rows, total):
    return Fetched("u", 200, json.dumps({"Table": rows, "Table1": [{"ROWCNT": total}]}).encode())


def test_pagination_reads_every_page_and_removes_duplicates(monkeypatch):
    first, second, third = ROWS[0], ROWS[1], ROWS[2]
    pages = iter([_page([first, second], 4), _page([second, third], 4), _page([ROWS[3]], 4)])
    seen = []

    def fake_get(_session, params):
        seen.append(params["pageno"])
        return next(pages)

    monkeypatch.setattr(bse, "_get", fake_get)
    got = bse.fetch_window("500325", date(2026, 8, 1), date(2026, 11, 1), delay=0)
    assert seen == [1, 2, 3]
    assert len(got) == 4  # `second` appeared twice
    assert [a.published_at for a in got] == sorted((a.published_at for a in got), reverse=True)


def test_an_empty_page_stops_the_loop(monkeypatch):
    monkeypatch.setattr(bse, "_get", lambda _s, p: _page([], 0))
    assert bse.fetch_window("500325", date(2026, 11, 1), date(2026, 11, 2), delay=0) == []


@pytest.fixture
def fake_fetch(monkeypatch):
    """Feed bse._get a scripted list of responses (or exceptions) and record the pauses it takes."""
    script, pauses = [], []

    def fetch(*_args, **_kwargs):
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(bse, "fetch", fetch)
    monkeypatch.setattr(bse.time, "sleep", pauses.append)
    return script, pauses


def test_a_transient_400_is_retried_after_a_pause(fake_fetch):
    script, pauses = fake_fetch
    script += [Fetched("u", 400, b"bad request"), Fetched("u", 200, b'{"Table": []}')]
    assert bse._get(object(), {}).ok
    assert pauses == [1.0]


def test_connection_errors_are_retried_too(fake_fetch):
    script, pauses = fake_fetch
    script += [FetchError("ConnectionResetError"), FetchError("ReadTimeout"), Fetched("u", 200, b"{}")]
    assert bse._get(object(), {}).ok
    assert pauses == [1.0, 3.0]


def test_it_gives_up_after_three_attempts_and_says_why(fake_fetch):
    script, pauses = fake_fetch
    script += [Fetched("u", 400, b"")] * 3
    with pytest.raises(FetchError, match="HTTP 400"):
        bse._get(object(), {})
    assert script == [] and pauses == [1.0, 3.0]


def test_a_403_block_is_not_retried(fake_fetch):
    script, pauses = fake_fetch
    script += [Fetched("u", 403, b"Access Denied"), Fetched("u", 200, b"{}")]
    with pytest.raises(FetchError, match="HTTP 403"):
        bse._get(object(), {})
    assert len(script) == 1 and pauses == []  # we did not hammer a server that said no


def test_a_single_request_cannot_span_more_than_365_days():
    with pytest.raises(ValueError):
        bse.fetch_window("500325", date(2025, 1, 1), date(2026, 11, 1))


def test_long_spans_are_split_into_contiguous_windows(monkeypatch):
    calls = []
    monkeypatch.setattr(bse, "fetch_window", lambda code, lo, hi, **kw: calls.append((lo, hi)) or [])
    start, end = date(2024, 9, 1), date(2026, 11, 15)
    bse.fetch_announcements("500325", start, end, delay=0)
    assert calls[0][1] == end and calls[-1][0] == start
    assert all((hi - lo).days <= bse.MAX_SPAN_DAYS for lo, hi in calls)
    for (lo, _), (_, next_hi) in zip(calls, calls[1:]):
        assert next_hi == lo - timedelta(days=1)  # no gap and no overlap between windows
    assert len(calls) == 3
