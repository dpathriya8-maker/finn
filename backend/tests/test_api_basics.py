"""Walking-skeleton API tests: /health shape, CORS allow-list, per-IP rate limit, security helpers."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import validate_ticker
from app.core.settings import parse_origins
from app.main import create_app


def make_client(monkeypatch, **env):
    for name in ("ALLOWED_ORIGINS", "RATE_LIMIT_DEFAULT", "ADMIN_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return TestClient(create_app())


def test_health_shape(monkeypatch):
    body = make_client(monkeypatch).get("/health").json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["time_ist"].endswith("+05:30")


def test_cors_allows_configured_and_local_origins_only(monkeypatch):
    client = make_client(monkeypatch, ALLOWED_ORIGINS="https://finn-demo.vercel.app/")

    def preflight(origin):
        return client.options(
            "/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        ).headers.get("access-control-allow-origin")

    assert preflight("https://finn-demo.vercel.app") == "https://finn-demo.vercel.app"
    assert preflight("http://localhost:3000") == "http://localhost:3000"
    assert preflight("https://evil.example") is None


def test_wildcard_origin_is_never_accepted():
    assert "*" not in parse_origins("*,https://a.example")


def test_rate_limit_hits_default_routes_but_not_health(monkeypatch):
    client = make_client(monkeypatch, RATE_LIMIT_DEFAULT="3/minute")
    assert [client.get("/").status_code for _ in range(4)] == [200, 200, 200, 429]
    assert client.get("/health").status_code == 200


def test_429_still_carries_cors_headers(monkeypatch):
    client = make_client(monkeypatch, RATE_LIMIT_DEFAULT="1/minute")
    headers = {"Origin": "http://localhost:3000"}
    client.get("/", headers=headers)
    limited = client.get("/", headers=headers)
    assert limited.status_code == 429
    assert limited.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.parametrize("raw, expected", [("reliance", "RELIANCE"), (" M&M ", "M&M"), ("BAJAJ-AUTO", "BAJAJ-AUTO")])
def test_valid_tickers(raw, expected):
    assert validate_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", "A" * 21, "RELIANCE.NS", "../etc", "AB CD", "X;DROP", "ÅBC"])
def test_invalid_tickers_are_rejected(raw):
    with pytest.raises(HTTPException) as err:
        validate_ticker(raw)
    assert err.value.status_code == 422
