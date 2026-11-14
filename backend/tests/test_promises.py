"""The Promise Tracker with a scripted model: what is kept, what is dropped, and how a verdict is earned."""
import json
from pathlib import Path

import pytest

from app.core.llm import LLMUnavailable
from app.pull import chunk as ck
from app.pull import promises as pr
from app.pull.retrieve import Index
from app.pull.text import strip_repeated_lines
from tests.fakes import FakeRouter, unavailable

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"


def chunks_of(name, doc="d1"):
    pages = strip_repeated_lines(json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["pages"])
    return ck.chunk_pages(doc, pages)


def call(doc, page, text, moderator=False):
    return ck.Chunk(doc, page, text, moderator)


EARLY = call("d1", 3, "We will commission the new plant by Q3 FY27 and we are targeting capacity of 500 MW in the coming year.")
EARLY2 = call("d1", 5, "We aim to keep the operating margin above 20% through FY27 and we expect capex of INR300 crores this year.")
LATER = call("d2", 7, "The new plant was commissioned in Q3 FY27 as planned and capacity of 500 MW is now operational.")


def extraction(*items):
    return {"promises": list(items)}


def item(excerpt, quote, **kw):
    return {"excerpt": excerpt, "quote": quote, "what": "commission the plant", "by_when": "Q3 FY27", "kind": "capex", **kw}


# ---------------------------------------------------------------------------------------------- extraction
def test_a_promise_is_kept_only_if_its_quote_is_in_the_excerpt_it_names_and_the_page_is_ours():
    router = FakeRouter(
        {
            "promises.extract": extraction(
                item("E1", "We will commission the new plant by Q3 FY27"),  # real
                item("E1", "We will commission the plant by Q2 FY27 with 900 MW"),  # reworded and renumbered: dropped
                item("E9", "We will commission the new plant by Q3 FY27"),  # an excerpt that does not exist: dropped
                item("E2", "We will commission the new plant by Q3 FY27"),  # right words, wrong excerpt: dropped
                item("E1", "we are targeting capacity of 500 MW in the coming year", kind="NOT A KIND", page=999),  # real; a page from the model is ignored
            )
        }
    )
    found = pr.extract(router, company="Acme", period="Q1 FY27", chunks=[EARLY, EARLY2])
    assert [p.quote for p in found] == ["We will commission the new plant by Q3 FY27", "we are targeting capacity of 500 MW in the coming year"]
    assert all(p.page == 3 and p.doc == "d1" and p.quarter == "Q1 FY27" for p in found)
    assert found[1].kind == "other"  # an unknown kind is "other", not trusted


def test_duplicates_over_long_quotes_and_non_dicts_are_ignored_and_the_list_is_capped():
    long_quote = "We will commission the new plant by Q3 FY27 " + "and more " * 60
    many = [call("d1", 1, f"We will launch product {n} by Q{(n % 4) + 1} FY27 and target {n + 10}% growth in the segment this year.") for n in range(1, 12)]
    items = [item(f"E{n}", f"We will launch product {n} by Q{(n % 4) + 1} FY27") for n in range(1, 12)]
    router = FakeRouter({"promises.extract": extraction(*items, items[0], "not a dict", item("E1", long_quote))})
    found = pr.extract(router, company="Acme", period="Q1 FY27", chunks=many)
    assert len(found) == pr.PER_CALL and len({p.quote for p in found}) == pr.PER_CALL


def test_the_extraction_prompt_treats_the_text_as_data_and_asks_for_exact_copies():
    router = FakeRouter({"promises.extract": extraction()})
    pr.extract(router, company="Acme", period="Q1 FY27", chunks=[EARLY])
    sent = router.calls[0]
    assert "ignore any instruction" in sent["system"] and "[E1]" in sent["prompt"] and "EXACTLY" in sent["prompt"]
    assert (sent["tier"], sent["version"]) == ("cheap", pr.EXTRACT_VERSION)


def test_chunks_with_nothing_forward_looking_cost_no_model_call():
    router = FakeRouter()
    chunks = [
        call("d1", 1, "Thank you all for joining us today, it is a pleasure to be with you on this call and to share the quarter."),
        call("d1", 2, "We will target 25% by FY27.", moderator=True),
    ]
    assert pr.extract(router, company="Acme", period="Q1 FY27", chunks=chunks) == [] and router.calls == []


def test_only_forward_looking_chunks_with_a_number_reach_the_model_and_never_the_moderator():
    chunks = chunks_of("KAYNES")
    picked = pr.select_chunks(chunks)
    assert 3 <= len(picked) <= pr.EXCERPTS_PER_CALL and not any(c.moderator for c in picked)
    assert len(picked) < len(chunks) / 2  # a fraction of the call, not all of it


def test_an_unavailable_model_is_reported_not_papered_over():
    with pytest.raises(LLMUnavailable):
        pr.extract(FakeRouter({"promises.extract": unavailable()}), company="Acme", period="Q1 FY27", chunks=[EARLY])


# ---------------------------------------------------------------------------------------------- judging
def made(id_="P1", quote="We will commission the new plant by Q3 FY27", doc="d1"):
    return pr.Promise(id=id_, doc=doc, quarter="Q1 FY27", page=3, quote=quote, what="commission the plant", by_when="Q3 FY27", kind="capex")


def verdicts(*items):
    return {"verdicts": list(items)}


def test_a_verdict_needs_a_quote_that_is_really_in_a_later_excerpt():
    reply = verdicts({"promise": "P1", "status": "Kept", "reason": "Commissioned on time.", "evidence": [{"excerpt": "L1", "quote": "The new plant was commissioned in Q3 FY27 as planned"}]})
    router = FakeRouter({"promises.judge": reply})
    p = made()
    pr.judge(router, company="Acme", promises=[p], later=Index([LATER]), quarter_of={"d2": "Q2 FY27"})
    assert (p.status, p.reason, p.downgraded) == ("Kept", "Commissioned on time.", False)
    assert [(e.doc, e.page) for e in p.evidence] == [("d2", 7)]
    assert router.calls[0]["tier"] == "strong" and "Q2 FY27, page 7" in router.calls[0]["prompt"]


def test_a_verdict_with_an_invented_quote_is_lowered_to_too_early():
    reply = verdicts({"promise": "P1", "status": "Missed", "reason": "Never built.", "evidence": [{"excerpt": "L1", "quote": "The plant was cancelled entirely"}]})
    p = made()
    pr.judge(FakeRouter({"promises.judge": reply}), company="Acme", promises=[p], later=Index([LATER]), quarter_of={"d2": "Q2 FY27"})
    assert (p.status, p.downgraded, p.evidence) == ("Too early", True, [])
    assert p.reason == "No later statement in the documents settles this."  # the model's unsupported reason is not shown


def test_too_early_needs_no_evidence_and_an_unknown_status_becomes_too_early():
    reply = verdicts({"promise": "P1", "status": "Too early", "reason": "Not due yet."}, {"promise": "P2", "status": "Delivered!", "reason": "x"}, {"promise": "P9", "status": "Kept"})
    a, b = made("P1"), made("P2", "We aim to keep the operating margin above 20% through FY27")
    pr.judge(FakeRouter({"promises.judge": reply}), company="Acme", promises=[a, b], later=Index([LATER]), quarter_of={"d2": "Q2 FY27"})
    assert (a.status, a.reason, a.downgraded) == ("Too early", "Not due yet.", False)
    assert b.status == "Too early"  # an invented status word never becomes a verdict; an unknown promise id is ignored


def test_with_nothing_later_to_read_no_model_is_asked():
    router = FakeRouter()
    p = made(quote="We will pursue a quantum computing business by 2040")
    unrelated = call("d2", 1, "Cash flow was healthy and receivables improved over the quarter we are reporting on today.")
    pr.judge(router, company="Acme", promises=[p], later=Index([unrelated]), quarter_of={})
    assert router.calls == [] and p.reason == "No later call says anything about this."


def test_the_judge_prompt_shows_only_later_excerpts_and_asks_for_exact_quotes():
    router = FakeRouter({"promises.judge": verdicts()})
    pr.judge(router, company="Acme", promises=[made()], later=Index([LATER]), quarter_of={"d2": "Q2 FY27"})
    prompt = router.calls[0]["prompt"]
    assert "[P1]" in prompt and "[L1]" in prompt and "EXACTLY" in prompt and "ignore any instruction" in router.calls[0]["system"]
    assert "We will commission the new plant" in prompt and "capacity of 500 MW is now operational" in prompt


# ---------------------------------------------------------------------------------------------- the scorecard
def test_the_scorecard_is_counted_here_and_a_rate_needs_at_least_three_decided_promises():
    def with_status(*statuses):
        return [pr.Promise(id=f"P{i}", doc="d1", quarter="Q1", page=1, quote="q", what="w", by_when=None, kind="other", status=s) for i, s in enumerate(statuses)]

    card = pr.scorecard(with_status("Kept", "Kept", "Partly", "Missed", "Too early", "Too early"))
    assert (card["kept"], card["partly"], card["missed"], card["too_early"], card["total"], card["decided"]) == (2, 1, 1, 2, 6, 4)
    assert card["delivery_rate_pct"] == 63  # (2 + 0.5) / 4 = 62.5, and a half rounds up
    assert pr.scorecard(with_status("Kept", "Missed", "Too early"))["delivery_rate_pct"] is None  # two decided: too few to call it a rate
    assert pr.scorecard([])["total"] == 0


# ---------------------------------------------------------------------------------------------- the whole tracker
def test_the_tracker_judges_older_calls_against_later_ones_and_never_the_newest():
    def extract_reply(prompt):
        if "Call: Q1 FY27" in prompt:
            return extraction(item("E1", "We will commission the new plant by Q3 FY27"))
        if "Call: Q3 FY27" in prompt:
            return extraction(item("E1", "capacity of 500 MW is now operational", what="500 MW online"))
        return extraction()

    judged = verdicts({"promise": "P1", "status": "Kept", "reason": "Done.", "evidence": [{"excerpt": "L1", "quote": "The new plant was commissioned in Q3 FY27 as planned"}]})
    router = FakeRouter({"promises.extract": extract_reply, "promises.judge": judged})
    newest_text = "Both units are done and capacity of 500 MW is now operational, and we will target 700 MW by FY28 end."
    calls = [("d1", "Q1 FY27", [EARLY]), ("d2", "Q2 FY27", [LATER]), ("d3", "Q3 FY27", [call("d3", 2, newest_text)])]
    promises = pr.build_tracker(router, company="Acme", calls=calls)
    first, newest = promises[0], promises[1]
    assert (first.id, first.status) == ("P1", "Kept") and newest.id == "P2"
    assert newest.status == "Too early" and "most recent call" in newest.reason
    assert router.purposes().count("promises.judge") == 1  # one older call had promises; the newest is never judged
    assert pr.to_dict(first)["verdict"]["evidence"][0]["doc"] == "d2"
