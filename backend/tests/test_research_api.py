"""The research and ask routes against the real engine, with the exchanges, the downloader and the model faked."""
import json
import threading
import time
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.cache import Cache
from app.core.timeutil import IST
from app.main import create_app
from app.pull import ingest as ig
from app.pull import research as rs
from app.pull.engine import Engine
from app.sources.models import Announcement, Listing
from tests.fakes import FakeRouter
from tests.pdfs import make_transcript_pdf

BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
LISTING = Listing("ACME", "Acme Ltd", "INE000000001", "500325", "1")
LINE = "Management: we will commission the new plant by Q3 FY27 and we are targeting capacity of 500 MW and capex of INR300 crores in the coming year, which is well on track."
CALLS = [("a", date(2026, 2, 3), "Q3 FY26"), ("b", date(2026, 5, 9), "Q4 FY26"), ("c", date(2026, 8, 8), "Q1 FY27")]
FILES = {f"{BASE}{name}.pdf": make_transcript_pdf([f"{label} page one\n{LINE}\n" * 2, f"{label} page two\n{LINE}\n" * 2]) for name, _d, label in CALLS}
ANNOUNCEMENTS = [
    Announcement("bse", name, "Acme Ltd", "500325", "Company Update", "Earnings Call Transcript", f"{label} earnings call transcript", "", datetime(d.year, d.month, d.day, tzinfo=IST), f"{BASE}{name}.pdf", 300_000)
    for name, d, label in CALLS
]


def make_sources(cache, *, listing=LISTING, resolve=None):
    return lambda: ig.IngestSources(
        resolve=resolve or (lambda s: listing), bse_announcements=lambda c, a, b: ANNOUNCEMENTS, nse_announcements=lambda *a: [], pdf=lambda url: FILES[url],
        cache=cache, today=lambda: date(2026, 11, 15),
    )


def engine(tmp_path, *, router=None, cap=20, static=True, today=date(2026, 11, 15), resolve=None, listing=LISTING, inline=True, workers=1):
    cache = Cache(":memory:")
    (tmp_path / "static").mkdir(exist_ok=True)
    return Engine(
        sources_factory=make_sources(cache, listing=listing, resolve=resolve), router_factory=lambda: router, cache=cache,
        static_dir=(tmp_path / "static") if static else None, daily_cap=cap, today=lambda: today, run_inline=inline, workers=workers,
    )


def client(eng, monkeypatch, **env):
    for name in ("ALLOWED_ORIGINS", "RATE_LIMIT_DEFAULT", "RATE_LIMIT_GLOBAL", "ADMIN_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    rs._MEMO.clear()
    return TestClient(create_app(engine=eng))


# ---------------------------------------------------------------------------------------------- reading
def test_a_company_nobody_has_researched_is_a_200_with_a_state_the_app_can_act_on(tmp_path, monkeypatch):
    r = client(engine(tmp_path), monkeypatch).get("/research/ACME")
    assert r.status_code == 200 and r.json() == {"state": "none"} and r.headers["cache-control"] == "no-store"  # not a 404: the browser would log it as an error


def test_a_ticker_is_validated_and_upper_cased(tmp_path, monkeypatch):
    c = client(engine(tmp_path), monkeypatch)
    assert c.get("/research/bad%20ticker!").status_code == 422
    assert c.get("/research/" + "A" * 21).status_code == 422
    assert c.post("/research/%3Cscript%3E").status_code == 422
    assert c.get("/research/acme").json() == {"state": "none"} and c.get("/research/M&M").status_code == 200  # valid NSE symbols pass


def test_a_record_shipped_with_the_app_is_served_without_any_work(tmp_path, monkeypatch):
    eng = engine(tmp_path)
    (tmp_path / "static" / "BAJFINANCE.json").write_text(json.dumps({"symbol": "BAJFINANCE", "status": "statements_only"}), encoding="utf-8")
    r = client(eng, monkeypatch).get("/research/BAJFINANCE")
    assert r.status_code == 200 and r.json() == {"state": "ready", "record": {"symbol": "BAJFINANCE", "status": "statements_only"}}
    assert eng.cap_used() == 0


# ---------------------------------------------------------------------------------------------- fresh research
def test_post_researches_a_new_company_then_get_serves_it_from_the_cache(tmp_path, monkeypatch):
    eng = engine(tmp_path)
    c = client(eng, monkeypatch)
    first = c.post("/research/ACME")
    assert first.status_code == 200 and first.json()["state"] == "ready"
    record = first.json()["record"]
    assert record["status"] == "statements_only" and len(record["documents"]) == 3 and record["name"] == "Acme Ltd"
    assert c.get("/research/ACME").json()["record"] == record
    assert eng.cap_used() == 1
    again = c.post("/research/ACME")
    assert again.status_code == 200 and eng.cap_used() == 1  # a record that exists is never refused and never counted


def test_with_a_model_the_record_is_ready_and_says_which_models_ran(tmp_path, monkeypatch):
    router = FakeRouter({"promises.extract": {"promises": []}})
    r = client(engine(tmp_path, router=router), monkeypatch).post("/research/ACME").json()["record"]
    assert r["status"] == "ready" and r["model"]["ran"] and r["model"]["models"] == ["fake:fake-model"]


def test_a_company_with_no_documents_is_a_ready_answer_that_says_so_and_is_not_kept(tmp_path, monkeypatch):
    eng = engine(tmp_path, listing=None)
    r = client(eng, monkeypatch).post("/research/NOSUCH")
    assert r.status_code == 200 and r.json()["record"]["status"] == "no_documents" and "not on NSE's list" in r.json()["record"]["reason"]
    assert eng.cache.get("research:v1:NOSUCH") is None  # a transient failure must not be remembered as the answer


def test_a_crash_inside_research_becomes_a_reason_and_never_a_stack_trace(tmp_path, monkeypatch):
    def explode(symbol):
        raise RuntimeError("secret internal detail at /srv/app/x.py line 12")

    c = client(engine(tmp_path, resolve=explode), monkeypatch)
    c.post("/research/ACME")
    body = c.get("/research/ACME").json()
    assert body["state"] == "failed" and "RuntimeError" in body["reason"] and "secret internal" not in json.dumps(body) and "/srv/app" not in json.dumps(body)


def test_the_work_really_runs_in_the_background_and_the_app_can_watch_its_stage(tmp_path, monkeypatch):
    gate = threading.Event()

    def slow_resolve(symbol):
        gate.wait(timeout=10)
        return LISTING

    eng = engine(tmp_path, resolve=slow_resolve, inline=False)
    c = client(eng, monkeypatch)
    started = c.post("/research/ACME")
    assert started.status_code == 202 and started.json()["state"] == "running" and started.json()["stage"]
    assert c.get("/research/ACME").status_code == 202  # still running
    assert c.post("/research/ACME").status_code == 202 and eng.cap_used() == 1  # asking again does not start a second job
    gate.set()
    deadline = time.time() + 10
    while time.time() < deadline and c.get("/research/ACME").status_code == 202:
        time.sleep(0.05)
    assert c.get("/research/ACME").json()["state"] == "ready"


# ---------------------------------------------------------------------------------------------- the daily cap
def test_the_cap_refuses_fresh_work_but_never_cached_work_and_resets_the_next_day(tmp_path, monkeypatch):
    eng = engine(tmp_path, cap=2)
    c = client(eng, monkeypatch)
    assert c.post("/research/AAA").status_code == 200 and c.post("/research/BBB").status_code == 200
    refused = c.post("/research/CCC")
    assert refused.status_code == 429 and refused.json()["cap"] == 2 and "unaffected" in refused.json()["detail"]
    assert c.get("/research/AAA").status_code == 200 and c.post("/research/BBB").status_code == 200  # cached research is unlimited
    eng.today = lambda: date(2026, 11, 16)
    assert c.post("/research/CCC").status_code == 200


def test_a_cap_of_zero_closes_fresh_research_entirely(tmp_path, monkeypatch):
    assert client(engine(tmp_path, cap=0), monkeypatch).post("/research/AAA").status_code == 429


# ---------------------------------------------------------------------------------------------- ask
def test_ask_needs_research_first(tmp_path, monkeypatch):
    r = client(engine(tmp_path), monkeypatch).post("/ask", json={"ticker": "ACME", "question": "What is the capex plan?"})
    assert r.status_code == 409 and "Research ACME first" in r.json()["detail"]


def test_ask_without_a_model_returns_the_closest_passages_with_the_documents_they_come_from(tmp_path, monkeypatch):
    c = client(engine(tmp_path), monkeypatch)
    c.post("/research/ACME")
    r = c.post("/ask", json={"ticker": "acme", "question": "What is the capex plan for the new plant?"})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "passages" and "not an answer" in body["note"] and body["passages"]
    assert {d["id"] for d in body["documents"]} >= {body["passages"][0]["doc"]} and body["documents"][0]["url"].startswith("https://www.bseindia.com/")


def test_ask_with_a_model_answers_with_a_quote_from_the_documents(tmp_path, monkeypatch):
    quote = "we are targeting capacity of 500 MW and capex of INR300 crores"
    router = FakeRouter({"ask": {"answer": "Capex is INR300 crores.", "citations": [{"excerpt": "X1", "quote": quote}]}, "promises.extract": {"promises": []}})
    c = client(engine(tmp_path, router=router), monkeypatch)
    c.post("/research/ACME")
    body = c.post("/ask", json={"ticker": "ACME", "question": "What is the capex plan for the new plant?"}).json()
    assert body["status"] == "answered" and body["citations"][0]["quote"] == quote and body["documents"]


def test_a_question_the_documents_do_not_cover_says_so(tmp_path, monkeypatch):
    c = client(engine(tmp_path), monkeypatch)
    c.post("/research/ACME")
    body = c.post("/ask", json={"ticker": "ACME", "question": "What is the dividend policy in Gujarat?"}).json()
    assert body["status"] == "not_found" and body["note"] == "Not found in the documents." and body["documents"] == []


@pytest.mark.parametrize(
    "payload, code",
    [
        ({"ticker": "ACME", "question": "hi"}, 422),  # too short
        ({"ticker": "ACME", "question": "x" * 301}, 422),  # too long
        ({"ticker": "ACME"}, 422),  # missing
        ({"ticker": "bad ticker", "question": "What is the capex plan?"}, 422),
        ({"ticker": "ACME", "question": "x" * 2001}, 422),
    ],
)
def test_a_bad_ask_is_refused_with_a_clear_status(tmp_path, monkeypatch, payload, code):
    c = client(engine(tmp_path), monkeypatch)
    c.post("/research/ACME")
    assert c.post("/ask", json=payload).status_code == code


def test_an_ask_that_breaks_inside_is_a_plain_502_with_no_internals(tmp_path, monkeypatch):
    eng = engine(tmp_path)
    c = client(eng, monkeypatch)
    c.post("/research/ACME")
    eng.router_factory = lambda: (_ for _ in ()).throw(RuntimeError("traceback with /srv/app/secret.py"))
    r = c.post("/ask", json={"ticker": "ACME", "question": "What is the capex plan for the new plant?"})
    assert r.status_code == 502 and "secret.py" not in r.text and "traceback" not in r.text.lower()


# ---------------------------------------------------------------------------------------------- limits and headers
def test_fresh_research_is_rate_limited_per_ip_more_tightly_than_reading(tmp_path, monkeypatch):
    c = client(engine(tmp_path, cap=100), monkeypatch)
    codes = [c.post(f"/research/T{n}").status_code for n in range(8)]
    assert codes[:6] == [200] * 6 and codes[6:] == [429, 429]
    assert c.get("/research/T0").status_code == 200  # reading has its own, larger allowance


def test_ask_is_rate_limited_per_ip(tmp_path, monkeypatch):
    c = client(engine(tmp_path), monkeypatch)
    c.post("/research/ACME")
    codes = [c.post("/ask", json={"ticker": "ACME", "question": "What is the capex plan?"}).status_code for _ in range(12)]
    assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]


def test_the_browser_origin_is_allowed_on_these_routes_and_a_429_still_carries_cors(tmp_path, monkeypatch):
    c = client(engine(tmp_path, cap=100), monkeypatch, ALLOWED_ORIGINS="https://finn-demo.vercel.app")
    origin = {"Origin": "https://finn-demo.vercel.app"}
    assert c.get("/research/ACME", headers=origin).headers["access-control-allow-origin"] == "https://finn-demo.vercel.app"
    for n in range(6):
        c.post(f"/research/T{n}", headers=origin)
    limited = c.post("/research/T6", headers=origin)
    assert limited.status_code == 429 and limited.headers["access-control-allow-origin"] == "https://finn-demo.vercel.app"
    assert c.get("/research/ACME", headers={"Origin": "https://evil.example"}).headers.get("access-control-allow-origin") is None


def test_the_limits_count_per_endpoint_so_a_different_ticker_does_not_reset_them(tmp_path, monkeypatch):
    c = client(engine(tmp_path, cap=100), monkeypatch)
    assert [c.post(f"/research/SAME{n}").status_code for n in range(7)][-1] == 429  # seven different tickers, one allowance


def test_one_address_cannot_exceed_the_global_ceiling_across_routes(tmp_path, monkeypatch):
    c = client(engine(tmp_path), monkeypatch, RATE_LIMIT_GLOBAL="5/minute")
    codes = [c.get(f"/research/T{n}").status_code for n in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]
    assert c.get("/health").status_code == 200  # the health check is never throttled


# ---------------------------------------------------------------------------------------------- the shipped corpus
def test_ask_works_for_a_company_whose_documents_ship_with_the_app_even_without_a_record_on_the_server(tmp_path, monkeypatch):
    from app.pull import corpus_store

    donor = engine(tmp_path)
    c = client(donor, monkeypatch)
    c.post("/research/ACME")  # reads the documents once
    corpus = ig.ingest("ACME", make_sources(donor.cache)())
    saved = tmp_path / "corpus"
    corpus_store.save(corpus, saved)

    fresh = Engine(
        sources_factory=lambda: ig.IngestSources(resolve=lambda s: None, bse_announcements=lambda *a: [], nse_announcements=lambda *a: [], pdf=lambda u: (_ for _ in ()).throw(AssertionError("no download")), cache=None, corpus_dir=saved),
        router_factory=lambda: None, cache=None, static_dir=None, corpus_dir=saved, run_inline=True,
    )
    rs._MEMO.clear()
    body = TestClient(create_app(engine=fresh)).post("/ask", json={"ticker": "ACME", "question": "What is the capex plan for the new plant?"}).json()
    assert body["status"] == "passages" and body["passages"] and body["documents"]
    other = TestClient(create_app(engine=fresh)).post("/ask", json={"ticker": "OTHER", "question": "What is the capex plan for the new plant?"})
    assert other.status_code == 409  # nothing shipped and nothing researched for this one
    rs._MEMO.clear()


# ---------------------------------------------------------------------------------------------- two requests at once
def test_two_simultaneous_requests_for_the_same_ticker_start_one_job_and_count_once(tmp_path):
    release = threading.Event()
    starts = []

    def slow_resolve(symbol):
        starts.append(symbol)
        release.wait(timeout=10)
        return LISTING

    eng = engine(tmp_path, resolve=slow_resolve, inline=False, workers=2, cap=5)
    real_cap_used = eng.cap_used

    def slow_cap_used():  # widen the window between "is anything running?" and "start a job", so an unlocked start would be caught
        time.sleep(0.02)
        return real_cap_used()

    eng.cap_used = slow_cap_used
    results = []
    barrier = threading.Barrier(8)

    def post():
        barrier.wait()
        try:
            results.append(eng.start("ACME")["state"])
        except Exception as exc:  # a failure here would be the bug
            results.append(repr(exc))

    threads = [threading.Thread(target=post) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    release.set()
    assert results == ["running"] * 8 and eng.cap_used() == 1  # eight at once: one job, one count
    deadline = time.time() + 10
    while time.time() < deadline and eng.state("ACME")["state"] != "ready":
        time.sleep(0.05)
    assert eng.state("ACME")["state"] == "ready" and starts == ["ACME"]
