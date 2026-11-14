"""GET /debug/sources is admin-only (CLAUDE.md section 8)."""
from fastapi.testclient import TestClient

from app.main import create_app


def client(monkeypatch, admin_token=None):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    if admin_token:
        monkeypatch.setenv("ADMIN_TOKEN", admin_token)
    return TestClient(create_app())


def test_closed_when_no_token_is_configured(monkeypatch):
    c = client(monkeypatch)
    assert c.get("/debug/sources").status_code == 403
    assert c.get("/debug/sources", headers={"X-Admin-Token": "anything"}).status_code == 403


def test_rejects_a_missing_or_wrong_token(monkeypatch):
    c = client(monkeypatch, "s3cret-token")
    assert c.get("/debug/sources").status_code == 403
    assert c.get("/debug/sources", headers={"X-Admin-Token": "wrong"}).status_code == 403


def test_runs_the_probes_with_the_right_token(monkeypatch):
    monkeypatch.setattr("app.api.debug.report", lambda symbol: {"symbol": symbol, "results": []})
    c = client(monkeypatch, "s3cret-token")
    ok = c.get("/debug/sources?symbol=kaynes", headers={"X-Admin-Token": "s3cret-token"})
    assert ok.status_code == 200 and ok.json()["symbol"] == "KAYNES"


def test_bad_tickers_are_rejected_even_with_the_right_token(monkeypatch):
    c = client(monkeypatch, "s3cret-token")
    bad = c.get("/debug/sources?symbol=../etc/passwd", headers={"X-Admin-Token": "s3cret-token"})
    assert bad.status_code == 422


def test_the_route_is_not_advertised_in_the_api_docs(monkeypatch):
    schema = client(monkeypatch).get("/openapi.json").json()
    assert not any(path.startswith("/debug") for path in schema["paths"])
