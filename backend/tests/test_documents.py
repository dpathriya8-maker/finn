"""Downloading a filing: only through the safe fetch, and only a real PDF counts. No network."""
import pytest

from app.core.http import BlockedUrl, Fetched, FetchError
from app.sources import documents

LIVE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/abc.pdf"
HISTORY = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/abc.pdf"
NSE = "https://nsearchives.nseindia.com/corporate/RELIANCE_15112026.pdf"
PDF = b"%PDF-1.7 pretend this is a filing"


def reply(status, content=PDF):
    return Fetched("u", status, content)


def getter(answers):
    seen = []

    def get(url, **kwargs):
        seen.append((url, kwargs))
        return answers[url]

    get.seen = seen
    return get


def test_a_pdf_is_returned_and_bse_is_asked_the_way_bse_requires():
    get = getter({LIVE: reply(200)})
    assert documents.fetch_pdf(LIVE, get=get) == PDF
    headers = get.seen[0][1]["headers"]
    assert {"User-Agent", "Referer", "Origin", "Accept"} <= set(headers)  # BSE answers 403 without all four
    assert headers["Accept"].startswith("application/pdf")


def test_a_bse_filing_that_has_moved_to_the_archive_is_found_there():
    get = getter({LIVE: reply(404, b""), HISTORY: reply(200)})
    assert documents.fetch_pdf(LIVE, get=get) == PDF
    assert [u for u, _ in get.seen] == [LIVE, HISTORY]


def test_and_the_other_way_round():
    get = getter({HISTORY: reply(404, b""), LIVE: reply(200)})
    assert documents.fetch_pdf(HISTORY, get=get) == PDF
    assert [u for u, _ in get.seen] == [HISTORY, LIVE]


def test_a_filing_that_is_nowhere_says_so():
    get = getter({LIVE: reply(404, b""), HISTORY: reply(404, b"")})
    with pytest.raises(FetchError, match="HTTP 404"):
        documents.fetch_pdf(LIVE, get=get)


def test_a_page_that_is_not_a_pdf_is_not_accepted_even_with_status_200():
    get = getter({LIVE: reply(200, b"<html>Access Denied</html>"), HISTORY: reply(200, b"<html>nope</html>")})
    with pytest.raises(FetchError, match="not a PDF"):
        documents.fetch_pdf(LIVE, get=get)


def test_an_nse_file_is_asked_for_with_nses_headers_and_only_once():
    get = getter({NSE: reply(200)})
    assert documents.fetch_pdf(NSE, get=get) == PDF
    assert len(get.seen) == 1
    headers = get.seen[0][1]["headers"]
    assert "nseindia.com" in headers["Referer"] and "Origin" not in headers


@pytest.mark.parametrize(
    "url",
    ["https://evil.example.com/a.pdf", "http://www.bseindia.com/xml-data/corpfiling/AttachLive/a.pdf", "https://127.0.0.1/a.pdf", "https://www.bseindia.com.evil.example/a.pdf"],
)
def test_the_real_fetch_refuses_anything_off_the_allow_list_before_touching_the_network(url):
    with pytest.raises(BlockedUrl):
        documents.fetch_pdf(url)  # the default getter is the safe fetch; it checks the URL first
