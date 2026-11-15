"""The Promise Tracker with a scripted model: what is kept, what is dropped, and how a verdict is earned.

The model only names an outcome and copies quotes and numbers; code decides when a promise is due, whether the model's
numbers are real, and which of Kept / Partly / Missed / Not followed up / Too early it is."""
import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.core.llm import LLMUnavailable
from app.pull import chunk as ck
from app.pull import promises as pr
from app.pull.retrieve import Index
from app.pull.text import strip_repeated_lines
from tests.fakes import FakeRouter, unavailable

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"
MADE = date(2026, 8, 4)  # the call the promises were made on (Q1 FY27)
LATEST = date(2027, 2, 10)  # the latest call on record (Q3 FY27): a Q3 FY27 promise is due by then, a FY28 one is not


def chunks_of(name, doc="d1"):
    pages = strip_repeated_lines(json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["pages"])
    return ck.chunk_pages(doc, pages)


def call(doc, page, text, moderator=False):
    return ck.Chunk(doc, page, text, moderator)


EARLY = call("d1", 3, "We will commission the new plant by Q3 FY27 and we are targeting capacity of 500 MW in the coming year.")
EARLY2 = call("d1", 5, "We aim to keep the operating margin above 20% through FY27 and we expect capex of INR300 crores this year.")
NO_TIME = call("d1", 6, "We will add capacity of 500 MW across our plants and we are targeting a margin of 20% on it, which is a good outcome for us.")
SLIPPED = call("d2", 8, "The new plant, which we said would be commissioned by Q3 FY27, has been delayed and is now pushed to next year.")
LATER = call("d2", 7, "The new plant was commissioned in Q3 FY27 as planned and capacity of 500 MW is now operational.")


def extraction(*items):
    return {"promises": list(items)}


def item(excerpt, quote, **kw):
    return {"excerpt": excerpt, "quote": quote, "what": "commission the plant", "by_when": "Q3 FY27", "target_period": "Q3 FY27", "kind": "capex", **kw}


def run_extract(router, chunks, **kw):
    return pr.extract(router, company="Acme", period="Q1 FY27", chunks=chunks, call_date=kw.pop("call_date", MADE), **kw)


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
    found = run_extract(router, [EARLY, EARLY2])
    assert [p.quote for p in found] == ["We will commission the new plant by Q3 FY27", "we are targeting capacity of 500 MW in the coming year"]
    assert all(p.page == 3 and p.doc == "d1" and p.quarter == "Q1 FY27" for p in found)
    assert found[1].kind == "other"  # an unknown kind is "other", not trusted


def test_duplicates_over_long_quotes_and_non_dicts_are_ignored_and_the_list_is_capped():
    long_quote = "We will commission the new plant by Q3 FY27 " + "and more " * 60
    many = [call("d1", 1, f"We will launch product {n} by Q{(n % 4) + 1} FY27 and target {n + 10}% growth in the segment this year.") for n in range(1, 12)]
    items = [item(f"E{n}", f"We will launch product {n} by Q{(n % 4) + 1} FY27", target_period="Q4 FY27") for n in range(1, 12)]
    router = FakeRouter({"promises.extract": extraction(*items, items[0], "not a dict", item("E1", long_quote))})
    found = run_extract(router, many)
    assert len(found) == pr.PER_CALL and len({p.quote for p in found}) == pr.PER_CALL


def test_the_due_date_is_read_from_the_quote_first_then_the_speakers_words_then_the_models_period():
    router = FakeRouter({"promises.extract": extraction(
        item("E1", "We will commission the new plant by Q3 FY27", target_period="FY99"),  # the quote says Q3 FY27: the model's own period is not used
        item("E2", "we are targeting a margin of 20%", target_period=None, by_when="second half"),  # no time words in the quote: the speaker's
        item("E2", "We will add capacity of 500 MW across our plants", by_when=None, target_period="FY28"),  # no words at all: the model's period
    )})
    first, second, third = run_extract(router, [EARLY, NO_TIME])
    assert (first.target_period, first.due) == ("FY99", date(2026, 12, 31))
    assert second.due == date(2027, 3, 31)  # "second half", said in August 2026: the half that ends in March 2027
    assert third.due == date(2028, 3, 31)


def test_the_model_reading_this_year_as_next_fiscal_year_is_overruled_by_the_quote():
    said = call("d1", 4, "this year, as we kind of go ahead, we are gunning for training almost 10 lakh people and we will expand it by 25%.")
    router = FakeRouter({"promises.extract": extraction(item("E1", "this year, as we kind of go ahead, we are gunning for training almost 10 lakh people", target_period="FY27", by_when="this year"))})
    (p,) = pr.extract(router, company="Acme", period="Q3 FY26", chunks=[said], call_date=date(2026, 2, 2))
    assert p.due == date(2026, 3, 31)  # a February call: this fiscal year is FY26, not the FY27 the model wrote


def test_the_speakers_open_ended_words_are_not_given_a_deadline_by_the_models_guess():
    router = FakeRouter({"promises.extract": extraction(item("E1", "We will add capacity of 500 MW across our plants", by_when="going forward", target_period="FY27"))})
    skipped = {}
    assert run_extract(router, [NO_TIME], skipped=skipped) == [] and skipped == {"no_deadline": 1}


def test_a_commitment_with_no_time_frame_is_not_tracked_and_is_counted():
    router = FakeRouter({"promises.extract": extraction(
        item("E1", "We will commission the new plant by Q3 FY27"),
        item("E2", "we are targeting a margin of 20%", target_period=None, by_when=None),
        item("E2", "We will add capacity of 500 MW across our plants", by_when="soon", target_period="FY27"),
    )})
    skipped = {}
    found = run_extract(router, [EARLY, NO_TIME], skipped=skipped)
    assert len(found) == 1 and skipped == {"no_deadline": 2}


def test_a_period_that_had_already_ended_on_the_day_of_the_call_is_not_a_promise_about_the_future():
    router = FakeRouter({"promises.extract": extraction(item("E1", "we are targeting a margin of 20%", target_period="Q4 FY26", by_when=None))})
    skipped = {}
    assert run_extract(router, [NO_TIME], skipped=skipped) == [] and skipped == {"already_past": 1}


def test_the_extraction_prompt_treats_the_text_as_data_asks_for_exact_copies_and_for_a_period():
    router = FakeRouter({"promises.extract": extraction()})
    run_extract(router, [EARLY])
    sent = router.calls[0]
    assert "ignore any instruction" in sent["system"] and "[E1]" in sent["prompt"] and "EXACTLY" in sent["prompt"]
    assert '"target_period"' in sent["prompt"] and "Call: Q1 FY27 (filed 2026-08-04)" in sent["prompt"]
    assert (sent["tier"], sent["version"]) == ("cheap", pr.EXTRACT_VERSION)


def test_chunks_with_nothing_forward_looking_cost_no_model_call():
    router = FakeRouter()
    chunks = [
        call("d1", 1, "Thank you all for joining us today, it is a pleasure to be with you on this call and to share the quarter."),
        call("d1", 2, "We will target 25% by FY27.", moderator=True),
    ]
    assert run_extract(router, chunks) == [] and router.calls == []


def test_only_forward_looking_chunks_with_a_number_reach_the_model_and_never_the_moderator():
    chunks = chunks_of("KAYNES")
    picked = pr.select_chunks(chunks)
    assert 3 <= len(picked) <= pr.EXCERPTS_PER_CALL and not any(c.moderator for c in picked)
    assert len(picked) < len(chunks) / 2  # a fraction of the call, not all of it


def test_an_unavailable_model_is_reported_not_papered_over():
    with pytest.raises(LLMUnavailable):
        run_extract(FakeRouter({"promises.extract": unavailable()}), [EARLY])


# ---------------------------------------------------------------------------------------------- judging
def made(id_="P1", quote="We will commission the new plant by Q3 FY27", due=date(2026, 12, 31), what="commission the plant", doc="d1"):
    return pr.Promise(id=id_, doc=doc, quarter="Q1 FY27", page=3, quote=quote, what=what, by_when="Q3 FY27", kind="capex", target_period="Q3 FY27", due=due)


def verdict(outcome="met", promise="P1", reason="Commissioned on time.", excerpt="L1", quote="The new plant was commissioned in Q3 FY27 as planned", **extra):
    evidence = [{"excerpt": excerpt, "quote": quote}] if quote else []
    return {"promise": promise, "outcome": outcome, "reason": reason, "evidence": evidence, **extra}


def judged(promises, *verdicts, chunks=(LATER,), latest=LATEST, quarter_of=None):
    router = FakeRouter({"promises.judge": {"verdicts": list(verdicts)}})
    pr.judge(router, company="Acme", promises=promises, later=Index(list(chunks)), quarter_of=quarter_of or {"d2": "Q2 FY27", "d3": "Q3 FY27"}, latest_call=latest)
    return router


def test_a_due_promise_a_later_call_shows_delivered_is_kept_and_cites_the_page():
    p = made()
    router = judged([p], verdict())
    assert (p.status, p.reason, p.downgraded, p.delayed) == ("Kept", "Commissioned on time.", False, False)
    assert [(e.doc, e.page) for e in p.evidence] == [("d2", 7)]
    assert router.calls[0]["tier"] == "strong" and "Q2 FY27, page 7" in router.calls[0]["prompt"]


def test_a_verdict_with_an_invented_quote_is_not_a_verdict_and_a_due_promise_becomes_not_followed_up():
    p = made()
    judged([p], verdict("missed", reason="Never built.", quote="The plant was cancelled entirely"))
    assert (p.status, p.downgraded, p.evidence) == ("Not followed up", True, [])
    assert p.reason == "A later call may touch on this, but no quote from it settles it."  # the model's unsupported reason is not shown, and it is not claimed that nothing was said


def test_not_mentioned_unknown_outcomes_and_skipped_promises_are_not_followed_up_when_due():
    a, b, c = made("P1"), made("P2"), made("P3")
    judged([a, b, c], verdict("not_mentioned", quote=None), verdict("Delivered!", promise="P2"))  # P3 gets no answer at all
    assert [p.status for p in (a, b, c)] == ["Not followed up"] * 3 and not a.downgraded


def test_with_nothing_relevant_in_any_later_call_no_model_is_asked():
    due, open_ = made("P1", quote="We will pursue a quantum computing business by 2040"), made("P2", quote="We will pursue a quantum computing business by 2040", due=date(2027, 12, 31))
    unrelated = call("d2", 1, "Cash flow was healthy and receivables improved over the quarter we are reporting on today.")
    router = judged([due, open_], chunks=[unrelated])
    assert router.calls == []
    assert due.status == "Not followed up" and due.reason == "Management has not mentioned this since the Q1 FY27 call."
    assert open_.status == "Too early" and "Not due until 31 Dec 2027" in open_.reason


def test_a_promise_not_yet_due_is_too_early_whatever_the_model_says_with_one_exception():
    open_due = date(2027, 12, 31)
    kept, partly, missed, delayed = (made(f"P{n}", due=open_due) for n in range(1, 5))
    q = "has been delayed and is now pushed to next year"
    judged(
        [kept, partly, missed, delayed],
        verdict("met", quote=q), verdict("partly_met", promise="P2", quote=q), verdict("missed", promise="P3", quote=q), verdict("postponed", promise="P4", quote=q, reason="The date has moved."),
        chunks=[SLIPPED],
    )
    assert [p.status for p in (kept, partly, missed)] == ["Too early"] * 3
    assert kept.reason.startswith("Not due until 31 Dec 2027") and "10 Feb 2027" in kept.reason
    # ... except that management's own words that it has slipped count at once
    assert (delayed.status, delayed.delayed, delayed.reason) == ("Missed", True, "The date has moved.")
    assert len(delayed.evidence) == 1


def test_a_promise_not_yet_due_costs_no_model_call_unless_a_later_excerpt_has_a_word_of_a_slip():
    quiet = made(due=date(2027, 12, 31))
    router = judged([quiet], chunks=[LATER])  # nothing later says it slipped: nothing could move it off "Too early"
    assert router.calls == [] and quiet.status == "Too early"
    worth_asking = made(due=date(2027, 12, 31))
    router = judged([worth_asking], verdict("not_mentioned", quote=None), chunks=[SLIPPED])
    assert len(router.calls) == 1 and worth_asking.status == "Too early"


def test_a_postponement_is_missed_delayed_and_a_reversal_is_missed():
    a, b, c = made("P1"), made("P2"), made("P3")
    q = "has been delayed and is now pushed to next year"
    judged([a, b, c], verdict("postponed", reason="Now conditional on January.", quote=q), verdict("reversed", promise="P2", quote=q), verdict("missed", promise="P3", quote=q), chunks=[SLIPPED])
    assert [(p.status, p.delayed) for p in (a, b, c)] == [("Missed", True), ("Missed", False), ("Missed", False)]


def test_a_miss_needs_a_word_of_a_miss_in_the_quote_it_cites():
    # A real failure: a quote about EXPANDING to 18 cities was cited as proof that the rollout was "postponed".
    p = made(quote="Now that we are more confident, we will over the next 12 months take this playbook to other cities", what="take the playbook to other cities", due=date(2026, 12, 31))
    chunk = call("d3", 20, "Now we're taking it national. We are slowly expanding; target is to now take it to 18 cities over the next few months, other cities too.")
    judged([p], verdict("postponed", quote="target is to now take it to 18 cities over the next few months"), chunks=[chunk])
    assert (p.status, p.downgraded, p.evidence) == ("Not followed up", True, [])
    q = made(quote=p.quote, what=p.what, due=p.due)
    judged([q], verdict("missed", quote="target is to now take it to 18 cities over the next few months"), chunks=[chunk])
    assert q.status == "Not followed up"  # the same for "missed" and "reversed"
    assert pr.has_slip_cue("is now pushed to next year") and pr.has_slip_cue("we have not yet launched it") and not pr.has_slip_cue("expanding to 18 cities")


def test_one_commitment_goes_to_the_model_at_a_time_with_the_passage_it_was_said_in():
    a, b = made("P1"), made("P2", quote="We aim to keep the operating margin above 20% through FY27", what="keep the operating margin above 20%")
    a.context = "99acres is our property portal. We will commission the new plant by Q3 FY27 and this matters for the segment."
    both = call("d2", 9, "The operating margin was above 20% for the year and the new plant was commissioned in Q3 FY27 as planned, FY27 is on track.")
    router = judged([a, b], verdict("met", quote="the new plant was commissioned in Q3 FY27 as planned"), verdict("met", promise="P2", quote="The operating margin was above 20% for the year"), chunks=[both])
    assert len(router.calls) == 2
    assert "[P1]" in router.calls[0]["prompt"] and "[P2]" not in router.calls[0]["prompt"]
    assert "the passage it was said in: \"99acres is our property portal" in router.calls[0]["prompt"]
    assert "the passage it was said in" not in router.calls[1]["prompt"]  # no context was stored for P2


def test_partly_met_is_partly():
    p = made()
    judged([p], verdict("partly_met", reason="Only one unit."))
    assert (p.status, p.reason) == ("Partly", "Only one unit.")


# --- numbers: the model reports them, the code checks they are in the quotes and decides
TRAINED = call("d2", 19, "More than 9 lakh people we have really trained under the programme during the year.")


def numeric(quote="this year, as we kind of go ahead, we are gunning for training almost 10 lakh people.", what="Train almost 10 lakh people"):
    return made(quote=quote, what=what, due=date(2026, 3, 31))


def test_a_number_short_of_the_promise_makes_it_partly_even_if_the_model_said_met():
    p = numeric()
    judged([p], verdict("met", reason="Trained almost 10 lakh.", quote="More than 9 lakh people we have really trained", target_value=10, actual_value=9, unit="lakh"), chunks=[TRAINED])
    assert p.status == "Partly" and p.numbers == {"target": 10.0, "actual": 9.0, "unit": "lakh", "lower_is_better": False, "attainment_pct": 90.0}
    assert p.reason == "Promised 10 lakh; a later call reports 9 lakh, 90% of the promise."  # written from the numbers, not by the model


@pytest.mark.parametrize(
    "target, actual, lower, expected",
    [(10, 10, False, "Kept"), (10, 12, False, "Kept"), (10, 9.99, False, "Kept"), (10, 9, False, "Partly"), (10, 7.5, False, "Partly"), (10, 7.4, False, "Missed"), (10, 5, False, "Missed"),
     (7.6, 7.55, True, "Kept"), (7.6, 8.5, True, "Partly"), (1.5, 3.5, True, "Missed")],
)
def test_the_rubric_met_75_to_99_percent_partly_below_that_missed(target, actual, lower, expected):
    p = made(quote=f"We will get to {target}% by Q3 FY27")
    chunk = call("d2", 7, f"We got to {actual}% by Q3 FY27 and the plant is running well for the year.")
    judged([p], verdict("met", quote=f"We got to {actual}%", target_value=target, actual_value=actual, unit="%", lower_is_better=lower), chunks=[chunk])
    assert p.status == expected, (p.status, p.numbers, p.reason)


def test_a_number_the_quotes_do_not_contain_is_ignored_and_the_outcome_word_stands():
    p = made(quote="We will commission 500 MW by Q3 FY27")
    judged([p], verdict("met", quote="capacity of 500 MW is now operational", target_value=900, actual_value=500, unit="MW"))  # 900 is in no quote
    assert (p.status, p.numbers) == ("Kept", None)
    q = made(quote="We will commission 500 MW by Q3 FY27")
    judged([q], verdict("met", quote="capacity of 500 MW is now operational", target_value=500, actual_value=450, unit="MW"))  # 450 is in no quote
    assert (q.status, q.numbers) == ("Kept", None)


def test_numbers_that_cannot_be_the_same_measure_do_not_override_the_outcome():
    p = made(quote="We will get to 100% by Q3 FY27")
    chunk = call("d2", 7, "We reached 3% in Q3 FY27 for the plant, which is a different measure.")
    judged([p], verdict("met", quote="We reached 3%", target_value=100, actual_value=3, unit="%"), chunks=[chunk])
    assert p.status == "Kept" and p.numbers is None  # 3% of the promise is not believable as the same thing


def test_a_postponement_is_missed_whatever_the_numbers_say():
    p = made(quote="We will get to 10% by Q3 FY27")
    chunk = call("d2", 7, "We reached 10% in Q3 FY27 but the launch itself is now pushed to next year for the plant.")
    judged([p], verdict("postponed", quote="the launch itself is now pushed to next year", target_value=10, actual_value=10, unit="%"), chunks=[chunk])
    assert (p.status, p.delayed) == ("Missed", True)


def test_a_number_in_the_models_wording_that_is_in_no_quote_replaces_the_reason_with_a_plain_one():
    p = made()
    judged([p], verdict("met", reason="Delivered 750 MW ahead of plan."))  # 750 is in neither quote
    assert p.status == "Kept" and p.reason == "Later calls show this was delivered."
    q = made()
    judged([q], verdict("met", reason="Capacity of 500 MW is operational."))  # 500 is in the evidence quote? it is not: the quote is shorter
    assert q.reason == "Later calls show this was delivered."
    r = made()
    judged([r], verdict("met", reason="Capacity of 500 MW is operational.", quote="capacity of 500 MW is now operational"))
    assert r.reason == "Capacity of 500 MW is operational."


def test_evidence_must_come_from_an_excerpt_listed_for_that_promise():
    plant = made("P1")
    router = judged([plant], verdict("met", excerpt="L9", quote="The new plant was commissioned in Q3 FY27 as planned"))  # there is no L9 for this promise
    assert plant.status == "Not followed up" and plant.downgraded and router.calls


def test_every_later_call_is_searched_so_a_call_that_speaks_to_it_is_never_crowded_out():
    crowd = [call("d2", n, f"The new plant commission plant Q3 FY27 update number {n} and more on the plant, the plant and the plant.") for n in range(1, 8)]
    answer = call("d3", 4, "The new plant is now commissioned, late for Q3 FY27, and running at full capacity after delays.")
    p = made()
    router = judged([p], verdict("met", excerpt="L1"), chunks=crowd + [answer])
    prompt = router.calls[0]["prompt"]
    assert "running at full capacity after delays" in prompt  # d3's excerpt is there although d2 alone has seven stronger ones
    assert prompt.count("[L") >= 1 + pr.LATER_PER_CALL


def test_the_judge_prompt_states_each_promises_state_shows_only_later_excerpts_and_asks_for_exact_quotes():
    due, open_ = made("P1"), made("P2", due=date(2027, 12, 31))
    router = judged([due, open_], chunks=[SLIPPED])
    first, second = router.calls[0]["prompt"], router.calls[1]["prompt"]
    assert "[P1]" in first and "[L1]" in first and "EXACTLY" in first and "ignore any instruction" in router.calls[0]["system"]
    assert "DUE (its time has passed" in first and "NOT YET DUE (due 31 Dec 2027)" in second
    assert "We will commission the new plant" in first and "has been delayed and is now pushed to next year" in first
    assert router.calls[0]["version"] == pr.JUDGE_VERSION


def test_the_moderators_words_are_never_evidence():
    operator = call("d2", 1, "The new plant Q3 FY27 commissioned, as the operator reads the announcement of the plant.", moderator=True)
    chunks = [c for c in [operator, LATER] if not c.moderator]
    assert chunks == [LATER]  # build_tracker drops the operator's chunks before indexing


# ---------------------------------------------------------------------------------------------- the scorecard
def test_the_scorecard_is_counted_here_and_a_rate_needs_at_least_three_decided_promises():
    def with_status(*statuses):
        return [pr.Promise(id=f"P{i}", doc="d1", quarter="Q1", page=1, quote="q", what="w", by_when=None, kind="other", status=s) for i, s in enumerate(statuses)]

    card = pr.scorecard(with_status("Kept", "Kept", "Partly", "Missed", "Not followed up", "Too early", "Too early"))
    assert (card["kept"], card["partly"], card["missed"], card["not_followed_up"], card["too_early"], card["total"], card["decided"]) == (2, 1, 1, 1, 2, 7, 4)
    assert card["delivery_rate_pct"] == 63  # (2 + 0.5) / 4 = 62.5, and a half rounds up; a promise not followed up is shown, not counted in the rate
    assert pr.scorecard(with_status("Kept", "Missed", "Too early"))["delivery_rate_pct"] is None  # two decided: too few to call it a rate
    assert pr.scorecard([])["total"] == 0


# ---------------------------------------------------------------------------------------------- the whole tracker
def test_the_tracker_judges_older_calls_against_later_ones_and_never_the_newest():
    def extract_reply(prompt):
        if "Call: Q1 FY27" in prompt:
            return extraction(item("E1", "We will commission the new plant by Q3 FY27"))
        if "Call: Q3 FY27" in prompt:
            return extraction(
                item("E1", "we will target 700 MW by FY28 end", what="700 MW", target_period=None, by_when=None),
                item("E1", "capacity of 500 MW is now operational", what="500 MW online", target_period=None, by_when=None),  # no time frame: not tracked
            )
        return extraction()

    judged_reply = {"verdicts": [verdict("met", reason="Done.")]}
    router = FakeRouter({"promises.extract": extract_reply, "promises.judge": judged_reply, "promises.verify": {"checks": [{"promise": "P1", "same_subject": True, "supports": True}]}})
    newest_text = "Both units are done and capacity of 500 MW is now operational, and we will target 700 MW by FY28 end."
    calls = [
        pr.Call("d1", "Q1 FY27", date(2026, 8, 4), [EARLY]),
        pr.Call("d2", "Q2 FY27", date(2026, 11, 5), [LATER]),
        pr.Call("d3", "Q3 FY27", LATEST, [call("d3", 2, newest_text)]),
    ]
    tracker = pr.build_tracker(router, company="Acme", calls=calls)
    first, newest = tracker.promises
    assert (first.id, first.status) == ("P1", "Kept") and newest.id == "P2"
    assert newest.status == "Too early" and "most recent call" in newest.reason
    assert tracker.latest_call.date == LATEST and tracker.no_deadline == 1
    assert router.purposes().count("promises.judge") == 1  # one older call had promises; the newest is never judged
    assert router.purposes().count("promises.verify") == 1  # and its one decided verdict was read a second time
    out = pr.to_dict(first)
    assert out["verdict"]["evidence"][0]["doc"] == "d2" and out["due"] == "2026-12-31" and out["target_period"] == "Q3 FY27"
    assert out["verdict"]["delayed"] is False and out["verdict"]["numbers"] is None


def test_an_unavailable_judge_model_stops_the_tracker_cleanly():
    router = FakeRouter({"promises.extract": extraction(item("E1", "We will commission the new plant by Q3 FY27")), "promises.judge": unavailable("quota")})
    calls = [pr.Call("d1", "Q1 FY27", date(2026, 8, 4), [EARLY]), pr.Call("d2", "Q2 FY27", LATEST, [LATER])]
    with pytest.raises(LLMUnavailable):
        pr.build_tracker(router, company="Acme", calls=calls)


def test_the_speakers_own_time_frame_beats_a_later_period_that_merely_appears_in_the_same_sentence():
    said = call("d1", 4, "This book will wind down to less than INR 1,500 crores by September '26 and that will lead to better profit in FY'27 as we said.")
    quote = "This book will wind down to less than INR 1,500 crores by September '26 and that will lead to better profit in FY'27"
    assert pr.resolve_due(quote, "by September '26", "FY27", date(2026, 5, 4)) == date(2026, 9, 30)
    assert pr.resolve_due(quote, None, None, date(2026, 5, 4)) == date(2027, 3, 31)  # with no by_when the whole quote is read: the latest period in it
    assert pr.resolve_due("We will grow volume 8% to 9% going forward", "going forward", "FY27", date(2026, 8, 4)) is None
    assert pr.resolve_due("We will launch", "by March", None, date(2026, 8, 4)) == date(2027, 3, 31)  # reworded by the model, not in the quote: still read
    assert said.page == 4


# ---------------------------------------------------------------------------------------------- the number reader
def test_numbers_are_read_even_when_glued_to_a_currency_but_fiscal_tokens_are_not_numbers():
    assert pr.numbers_in("now down to just INR2,400-odd crores") == [2400.0]
    assert pr.numbers_in("wind down to less than INR 1,500-odd crores by September '26") == [1500.0, 26.0]
    assert pr.numbers_in("Rs.9 lakh, 22% and 3.5 in Q1 FY27 and H2 FY'27 and CY2026") == [9.0, 22.0, 3.5]
    assert pr.numbers_in("Q1 FY27 and FY 28, H2") == []
    assert pr.numbers_in("grew 26%, 27% and 2,500, 3,000.") == [26.0, 27.0, 2500.0, 3000.0]


def test_a_book_that_was_to_fall_below_1500_crore_and_is_2400_is_missed_by_the_numbers_not_kept_on_the_models_word():
    p = made(quote="This book will wind down to less than INR 1,500-odd crores by September '26", what="wind the book down below INR 1,500 crores", due=date(2026, 9, 30))
    chunk = call("d2", 3, "The captive book continues to wind down in September and is now down to just INR2,400-odd crores as we are closing it out.")
    judged([p], verdict("met", reason="The book is winding down.", quote="is now down to just INR2,400-odd crores", target_value="1,500", actual_value="2,400", unit="crores", lower_is_better=True), chunks=[chunk])
    assert p.status == "Missed" and p.numbers["attainment_pct"] == 62.5
    assert p.reason == "Promised 1500 crores; a later call reports 2400 crores, 62.5% of the promise."


# ---------------------------------------------------------------------------------------------- finding the later mention
def test_a_later_chunk_that_shares_only_a_rare_name_with_the_promise_is_still_read():
    promise = made(quote="In Q2, we will kick off our VAE also.", what="Kick off VAE", due=date(2026, 9, 30))
    mention = call("d4", 13, "I am proud to announce that in September we started our VAE facility, and it was done in a record time and with utmost safety for everyone.")
    filler = [call("d4", n, f"Volume growth and margins were healthy in the quarter on page {n} as we told you, and costs were under control across the business.") for n in range(1, 30)]
    router = judged([promise], verdict("met", excerpt="L1", quote="in September we started our VAE facility"), chunks=filler + [mention])
    assert "in September we started our VAE facility" in router.calls[0]["prompt"]  # a single shared word, but a rare one: not "not mentioned"
    assert promise.status == "Kept"


def test_a_hyphenated_name_in_a_promise_meets_its_parts_on_the_page():
    from app.pull.retrieve import tokens

    assert {"vam-vae", "vam", "vae"} <= set(tokens("the VAM-VAE project")) and "vam" in tokens("VAM and VAE chemistry")
    page = Index([call("d4", 13, "the VAM and VAE chemistry is green and we started it in September of this year as planned by the team on the ground")])
    assert page.search("VAM-VAE backward integration project")


# ---------------------------------------------------------------------------------------------- the second reading
def decided(status="Kept", delayed=False, due=date(2026, 12, 31), id_="P1"):
    p = made(id_, due=due)
    p.status, p.delayed, p.reason = status, delayed, "Done."
    p.evidence = [pr.Evidence("d2", 7, "The new plant was commissioned in Q3 FY27 as planned")]
    return p


def checks(*items):
    return FakeRouter({"promises.verify": {"checks": list(items)}})


def test_a_verdict_whose_quote_is_not_about_the_same_thing_is_not_shown_as_decided():
    kept, missed = decided("Kept", id_="P1"), decided("Missed", id_="P2")
    router = checks({"promise": "P1", "same_subject": True, "supports": True}, {"promise": "P2", "same_subject": False, "supports": True})
    pr.verify(router, company="Acme", promises=[kept, missed], quarter_of={"d2": "Q2 FY27"}, latest_call=LATEST)
    assert kept.status == "Kept" and not kept.downgraded
    assert (missed.status, missed.downgraded, missed.evidence) == ("Not followed up", True, [])
    assert missed.reason == "A later call may touch on this, but no quote from it settles it."
    prompt = router.calls[0]["prompt"]
    assert "[P1]" in prompt and "[P2]" in prompt and "Q2 FY27, page 7" in prompt and "same_subject" in prompt
    assert (router.calls[0]["tier"], router.calls[0]["version"]) == ("strong", pr.VERIFY_VERSION)


def test_a_verdict_the_second_reading_does_not_answer_for_or_only_half_confirms_is_not_shown_as_decided():
    a, b, c = decided(id_="P1"), decided(id_="P2"), decided(id_="P3")
    router = checks({"promise": "P1", "same_subject": True, "supports": False}, {"promise": "P2", "same_subject": "true", "supports": "true"})  # P3: no answer
    pr.verify(router, company="Acme", promises=[a, b, c], quarter_of={}, latest_call=LATEST)
    assert [p.status for p in (a, b, c)] == ["Not followed up", "Kept", "Not followed up"]


def test_a_postponement_that_is_not_confirmed_goes_back_to_too_early_when_it_is_not_yet_due():
    p = decided("Missed", delayed=True, due=date(2027, 12, 31))
    pr.verify(checks({"promise": "P1", "same_subject": False, "supports": False}), company="Acme", promises=[p], quarter_of={}, latest_call=LATEST)
    assert (p.status, p.delayed) == ("Too early", False) and "Not due until 31 Dec 2027" in p.reason


def test_with_nothing_decided_the_second_reading_asks_no_model():
    undecided = made()
    router = checks()
    pr.verify(router, company="Acme", promises=[undecided], quarter_of={}, latest_call=LATEST)
    assert router.calls == []


def test_two_numbers_found_in_the_quotes_decide_even_when_the_model_says_missed_and_the_quote_has_no_word_of_a_miss():
    p = made(quote="We will get to 10% by Q3 FY27")
    chunk = call("d2", 7, "We got to 10% by Q3 FY27 and the plant is running well for the year.")
    judged([p], verdict("missed", quote="We got to 10%", target_value=10, actual_value=10, unit="%"), chunks=[chunk])
    assert p.status == "Kept" and p.numbers["attainment_pct"] == 100.0  # the arithmetic is not an opinion


def test_a_verdict_decided_by_numbers_is_not_put_to_the_model_again():
    p = decided("Kept")
    p.numbers = {"target": 10.0, "actual": 10.0, "unit": "%", "lower_is_better": False, "attainment_pct": 100.0}
    router = checks()
    pr.verify(router, company="Acme", promises=[p], quarter_of={}, latest_call=LATEST)
    assert router.calls == [] and p.status == "Kept"


def test_the_second_reading_is_shown_the_passage_each_commitment_was_said_in():
    p = decided("Kept")
    p.context = "99acres is our property portal and we expect billings growth to recover in Q1."
    router = checks({"promise": "P1", "same_subject": True, "supports": True})
    pr.verify(router, company="Acme", promises=[p], quarter_of={}, latest_call=LATEST)
    assert "the passage it was said in: \"99acres is our property portal" in router.calls[0]["prompt"]


def test_a_later_call_that_names_the_subject_only_in_the_lead_in_sentences_is_found():
    # The real case: "We expect billings growth to recover in Q1" is about 99acres, said two sentences earlier.
    context = ("During Q4, we undertook changes in the 99acres sales organization and tightened certain key processes. "
               "This had a one-time transitional impact on Q4 billings. We expect billings growth to recover in Q1 once again. 99acres continues to lead on traffic.")
    p = made(quote="We expect billings growth to recover in Q1 once again.", what="Expect billings growth to recover in Q1.", due=date(2026, 6, 30))
    p.context = context
    assert "99acres" in pr._lead_in(p) and "We expect billings" not in pr._lead_in(p)
    recruitment = [call("d3", n, f"Recruitment billings grew by over 17% in the quarter and billings growth was healthy, with page {n} showing the details of billings for the segment.") for n in range(1, 8)]
    property_portal = call("d3", 9, "Last quarter the 99acres billing growth was flattish. This quarter we saw a recovery to double digits as the sales changes took hold.")
    chunks = recruitment + [property_portal]

    without = made(quote=p.quote, what=p.what, due=p.due)  # the same promise with no passage stored: nothing in it names 99acres
    asked = judged([without], chunks=chunks)
    assert not asked.calls or "99acres billing growth was flattish" not in asked.calls[0]["prompt"]

    def cites_the_99acres_excerpt(prompt):
        found = re.search(r"\[(L\d+)\] \([^)]*\) Last quarter the 99acres", prompt)
        return {"verdicts": [verdict("met", excerpt=found.group(1), quote="This quarter we saw a recovery to double digits")]}

    router = FakeRouter({"promises.judge": cites_the_99acres_excerpt})
    pr.judge(router, company="Acme", promises=[p], later=Index(chunks), quarter_of={"d3": "Q1 FY27"}, latest_call=LATEST)
    assert p.status == "Kept" and p.evidence[0].page == 9  # offered to the judge only because of the lead-in sentences
