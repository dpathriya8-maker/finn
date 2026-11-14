"""The outbound-fetch guard: allow-list, redirects and the size cap (CLAUDE.md section 8)."""
import pytest

from app.core.http import BlockedUrl, FetchError, TooLarge, check_url, fetch

ALLOWED = [
    "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w",
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/a.pdf",
    "https://nsearchives.nseindia.in/corporate/a.pdf",
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
    "https://www.nseindia.com/api/corporate-announcements",
    "https://www.screener.in/company/ITC/",
    "https://query1.finance.yahoo.com/v8/finance/chart/ITC.NS",
]

BLOCKED = [
    "",
    "//api.bseindia.com/x",
    "http://api.bseindia.com/x",  # plain http
    "ftp://api.bseindia.com/x",
    "file:///etc/passwd",
    "https://evil.example/x",
    "https://bseindia.com.evil.example/x",  # allowed name used as a prefix
    "https://notbseindia.com/x",  # allowed name used as a suffix without a dot
    "https://127.0.0.1/x",
    "https://[::1]/x",
    "https://169.254.169.254/latest/meta-data/",  # cloud metadata address
    "https://user:secret@api.bseindia.com/x",
    "https://api.bseindia.com:8443/x",
]


@pytest.mark.parametrize("url", ALLOWED)
def test_allowed_hosts_pass(url):
    assert check_url(url) == url


@pytest.mark.parametrize("url", BLOCKED)
def test_everything_else_is_blocked(url):
    with pytest.raises(BlockedUrl):
        check_url(url)


class FakeResponse:
    def __init__(self, status=200, headers=None, chunks=(b"ok",)):
        self.status_code, self.headers, self._chunks = status, headers or {}, chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, _size):
        yield from self._chunks


class FakeSession:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_a_redirect_to_a_disallowed_host_is_refused_and_never_requested():
    session = FakeSession(FakeResponse(302, {"location": "https://evil.example/steal"}))
    with pytest.raises(BlockedUrl):
        fetch("https://www.bseindia.com/a.pdf", session=session)
    assert len(session.calls) == 1


def test_a_redirect_to_an_allowed_host_is_followed_without_the_original_params():
    session = FakeSession(
        FakeResponse(301, {"location": "https://www.nseindia.com/b"}),
        FakeResponse(200, chunks=(b"he", b"llo")),
    )
    result = fetch("https://www.bseindia.com/a", session=session, params={"q": "1"})
    assert result.ok and result.content == b"hello" and result.url == "https://www.nseindia.com/b"
    assert session.calls[0][1]["params"] == {"q": "1"}
    assert session.calls[1][1]["params"] is None


def test_redirect_loops_stop():
    loop = FakeResponse(302, {"location": "https://www.bseindia.com/a"})
    with pytest.raises(FetchError, match="too many redirects"):
        fetch("https://www.bseindia.com/a", session=FakeSession(*[loop] * 10))


def test_declared_size_over_the_cap_is_refused_before_reading():
    session = FakeSession(FakeResponse(200, {"content-length": "999999999"}))
    with pytest.raises(TooLarge):
        fetch("https://www.bseindia.com/a.pdf", session=session, max_bytes=1000)


def test_streamed_size_over_the_cap_is_refused_even_without_a_declared_length():
    session = FakeSession(FakeResponse(200, chunks=(b"x" * 600, b"x" * 600)))
    with pytest.raises(TooLarge):
        fetch("https://www.bseindia.com/a.pdf", session=session, max_bytes=1000)


def test_error_statuses_are_returned_not_raised():
    result = fetch("https://www.bseindia.com/a", session=FakeSession(FakeResponse(403, chunks=(b"denied",))))
    assert not result.ok and result.status == 403
