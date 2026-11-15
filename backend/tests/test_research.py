"""The research record end to end: real transcript text through synthetic PDFs, the downloader and the exchanges faked,
and the model scripted. What matters is what the record SAYS ran, and that nothing in it is unsupported."""
import json
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from app.core.cache import Cache
from app.core.timeutil import IST
from app.pull import ingest as ig
from app.pull import periods
from app.pull import promises as pr
from app.pull import research as rs
from app.pull.text import normalise, quote_is_in, strip_repeated_lines
from app.sources.models import Announcement, Listing
from tests.fakes import FakeRouter, unavailable
from tests.pdfs import make_transcript_pdf

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"
BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
LISTING = Listing("ACME", "Acme Ltd", "INE000000001", "500325", "1")
# Three real calls stand in for three quarters of one company.
CALLS = [("KAYNES", date(2026, 2, 3), "Q3 FY26"), ("BAJFINANCE", date(2026, 5, 9), "Q4 FY26"), ("RELIANCE", date(2026, 8, 8), "Q1 FY27")]


def pages_of(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["pages"]


@lru_cache(maxsize=None)
def pdf_bytes(name):
    return make_transcript_pdf(pages_of(name))  # built once: it is the slowest part of the suite


@lru_cache(maxsize=None)
def read_back(name):
    """The pages exactly as the pipeline sees them after downloading and reading that PDF (a font may change a glyph)."""
    return strip_repeated_lines(ig.read_pages(pdf_bytes(name)))


NAMES = {"d1": "KAYNES", "d2": "BAJFINANCE", "d3": "RELIANCE"}


def sources(*, n_calls=3, cache=None, listing=LISTING):
    chosen = CALLS[-n_calls:]
    announcements = [
        Announcement("bse", name, "Acme Ltd", "500325", "Company Update", "Earnings Call Transcript", f"{label} earnings call transcript", "", datetime(d.year, d.month, d.day, tzinfo=IST), f"{BASE}{name}.pdf", 400_000)
        for name, d, label in chosen
    ]
    files = {f"{BASE}{name}.pdf": pdf_bytes(name) for name, _d, _l in chosen}
    s = ig.IngestSources(resolve=lambda sym: listing, bse_announcements=lambda c, a, b: announcements, nse_announcements=lambda *a: [], pdf=lambda url: files[url], cache=cache, today=lambda: date(2026, 11, 15))
    return s


def first_excerpt_quote(prompt, prefix="E"):
    """A quote copied exactly from the first excerpt in a prompt: what a well-behaved model would return."""
    match = re.search(rf"\[{prefix}1\] \(.*?page \d+\) (.{{120}})", prompt)
    return match.group(1).rsplit(" ", 1)[0] if match else ""


def obedient_router():
    due = {"Call: Q3 FY26": "Q4 FY26", "Call: Q4 FY26": "Q1 FY27", "Call: Q1 FY27": "FY28"}  # the two older promises are due by the latest call; the newest is not

    def extract(prompt):
        period = next(target for marker, target in due.items() if marker in prompt)
        return {"promises": [{"excerpt": "E1", "quote": first_excerpt_quote(prompt), "what": "a commitment", "by_when": None, "target_period": period, "kind": "other"}]}

    def judge(prompt):
        ids = re.findall(r"^\[(P\d+)\]", prompt, re.M)
        return {"verdicts": [{"promise": pid, "outcome": "met", "reason": "As said.", "evidence": [{"excerpt": "L1", "quote": first_excerpt_quote(prompt, "L")}]} for pid in ids]}

    def verify(prompt):
        return {"checks": [{"promise": pid, "same_subject": True, "supports": True} for pid in re.findall(r"^\[(P\d+)\]", prompt, re.M)]}

    return FakeRouter({"promises.extract": extract, "promises.judge": judge, "promises.verify": verify})


# ---------------------------------------------------------------------------------------------- no model
def test_without_a_model_the_record_has_documents_and_statements_and_says_no_model_ran():
    record = rs.research("ACME", "Acme Ltd", sources=sources(), router=None)
    assert record["status"] == "statements_only" and record["model"] == {"ran": False, "reason": "No model is configured."}
    assert [d["period"] for d in record["documents"]] == ["Q3 FY26", "Q4 FY26", "Q1 FY27"] and [d["id"] for d in record["documents"]] == ["d1", "d2", "d3"]
    assert record["promises"] == [] and record["scorecard"] is None
    assert len(record["statements"]) >= 9  # a few from each call


def test_every_statement_in_the_record_is_a_verbatim_span_of_its_document_page():
    record = rs.research("ACME", "Acme Ltd", sources=sources(), router=None)
    for s in record["statements"]:
        assert quote_is_in(s["text"], read_back(NAMES[s["doc"]])[s["page"] - 1]), s
        assert s["quarter"] == {"d1": "Q3 FY26", "d2": "Q4 FY26", "d3": "Q1 FY27"}[s["doc"]]


def test_the_record_carries_what_a_reader_needs_to_find_each_document():
    d = rs.research("ACME", "Acme Ltd", sources=sources(), router=None)["documents"][0]
    assert d["url"].endswith("KAYNES.pdf") and d["pages"] == 20 and d["kind"] == "transcript" and len(d["sha256"]) == 64 and d["bytes"] > 1000


# ---------------------------------------------------------------------------------------------- with a model
def test_with_a_model_the_promises_are_verified_judged_and_counted(monkeypatch):
    # The fake model quotes the first words of real transcripts, which carry their own time words; pin the due date to the model's period.
    monkeypatch.setattr(pr, "resolve_due", lambda quote, by_when, target, call_date: periods.period_end(target, call_date))
    router = obedient_router()
    record = rs.research("ACME", "Acme Ltd", sources=sources(), router=router)
    assert record["status"] == "ready" and record["model"]["ran"] and record["model"]["models"] == ["fake:fake-model"]
    assert len(record["promises"]) == 3  # one per call
    older, newest = record["promises"][:2], record["promises"][2]
    assert [p["verdict"]["status"] for p in older] == ["Kept", "Kept"] and newest["verdict"]["status"] == "Too early"
    for p in record["promises"]:
        assert quote_is_in(p["quote"], read_back(NAMES[p["doc"]])[p["page"] - 1])  # the promise is on its page
        for e in p["verdict"]["evidence"]:
            assert quote_is_in(e["quote"], read_back(NAMES[e["doc"]])[e["page"] - 1])  # and so is the evidence
            assert e["doc"] > p["doc"]  # evidence comes from a LATER call
    assert record["scorecard"] == {
        "kept": 2, "partly": 0, "missed": 0, "not_followed_up": 0, "too_early": 1, "total": 3, "decided": 2, "delivery_rate_pct": None,
        "no_deadline": 0, "as_of": "2026-08-08", "as_of_call": "Q1 FY27",
    }
    assert [p["due"] for p in record["promises"]] == ["2026-03-31", "2026-06-30", "2028-03-31"]
    assert router.purposes().count("promises.extract") == 3 and router.purposes().count("promises.judge") == 2 and router.purposes().count("promises.verify") == 1


def test_the_record_says_how_much_the_model_did_and_how_much_the_cache_saved(monkeypatch):
    monkeypatch.setattr(pr, "resolve_due", lambda quote, by_when, target, call_date: periods.period_end(target, call_date))
    record = rs.research("ACME", "Acme Ltd", sources=sources(), router=obedient_router())
    assert record["model"]["calls"] == 6 and record["model"]["cache_hits"] == 0 and record["model"]["tokens_in"] == 600


def test_a_model_that_goes_down_leaves_a_statements_record_with_the_reason():
    record = rs.research("ACME", "Acme Ltd", sources=sources(), router=FakeRouter({"promises.extract": unavailable("quota exhausted")}))
    assert record["status"] == "statements_only" and record["model"]["ran"] is False and "quota exhausted" in record["model"]["reason"]
    assert record["statements"] and record["promises"] == []  # what could be done without a model is still there


def test_a_promise_needs_a_later_call_so_one_transcript_is_not_enough():
    router = obedient_router()
    record = rs.research("ACME", "Acme Ltd", sources=sources(n_calls=1), router=router)
    assert record["status"] == "statements_only" and "fewer than two transcripts" in record["model"]["reason"] and router.calls == []


# ---------------------------------------------------------------------------------------------- nothing to read
def test_a_company_with_no_documents_gets_a_record_that_says_so_not_an_error():
    record = rs.research("NOSUCH", "No Such Ltd", sources=sources(listing=None), router=obedient_router())
    assert record["status"] == "no_documents" and "not on NSE's list" in record["reason"]
    assert record["documents"] == [] and record["statements"] == [] and record["model"]["ran"] is False


# ---------------------------------------------------------------------------------------------- for Ask
def test_the_index_for_ask_is_built_once_per_company_and_forgets_the_oldest():
    rs._MEMO.clear()
    calls = []
    s = sources()
    original = s.resolve
    s.resolve = lambda sym: (calls.append(sym), original(sym))[1]
    first, corpus = rs.corpus_index("ACME", s)
    again, _ = rs.corpus_index("ACME", s)
    assert first is again and calls == ["ACME"] and len(corpus.documents) == 3
    for n in range(rs.MEMO_SIZE):
        rs.corpus_index(f"OTHER{n}", s)
    assert len(rs._MEMO) == rs.MEMO_SIZE and "ACME" not in rs._MEMO  # the oldest was forgotten
    rs._MEMO.clear()


def test_the_cache_makes_a_second_run_download_nothing_and_ask_can_use_the_same_documents():
    rs._MEMO.clear()
    cache = Cache(":memory:")
    rs.research("ACME", "Acme Ltd", sources=sources(cache=cache), router=None)
    s2 = sources(cache=cache)
    s2.pdf = lambda url: (_ for _ in ()).throw(AssertionError("must come from the cache"))
    index, corpus = rs.corpus_index("ACME", s2)
    assert index.search("capex for OSAT and PCB")[0].chunk.doc == "d1" and normalise(corpus.documents[0].title).startswith("Q3 FY26")
    rs._MEMO.clear()
