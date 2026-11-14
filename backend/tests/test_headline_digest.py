"""Headlines, results de-duplication, and the fully classified item the pipeline writes."""
import json
from pathlib import Path

from app.push.digest import announcement_item, dedupe_results
from app.push.headline import first_sentence, make_headline, strip_boilerplate, tidy_case
from app.sources import bse

FIXTURES = Path(__file__).parent / "fixtures"
ROWS = [bse.parse_row(r) for r in json.loads((FIXTURES / "bse_announcements.json").read_text(encoding="utf-8"))["Table"]]
RESULTS, TRANSCRIPT, BAJAJ_TRANSCRIPT, PREFIXED = ROWS


# ---------- headlines ----------
def test_exchange_boilerplate_is_removed_from_the_front_of_a_subject():
    assert strip_boilerplate("Announcement under Regulation 30 (LODR)-Credit Rating") == "Credit Rating"
    assert strip_boilerplate("Board Meeting Outcome for Outcome Of Board Meeting Held On 19 October 2026") == (
        "Outcome Of Board Meeting Held On 19 October 2026"
    )
    assert strip_boilerplate("Results- Financial Results For 30/09/2026") == "Financial Results For 30/09/2026"


def test_title_case_gets_small_words_and_ordinals_tidied():
    assert tidy_case("Unaudited Financial Results For The Quarter And Half Year Ended On 30Th September, 2026") == (
        "Unaudited Financial Results for the Quarter and Half Year Ended on 30th September, 2026"
    )


def test_all_caps_becomes_title_case_and_keeps_acronyms():
    assert tidy_case("OUTCOME OF BOARD MEETING HELD ON 12TH NOVEMBER 2026") == "Outcome of Board Meeting Held on 12th November 2026"
    assert "SEBI" in tidy_case("DISCLOSURE UNDER SEBI TAKEOVER REGULATIONS")


def test_ordinary_sentences_are_left_alone():
    sentence = "The Company has executed a share purchase agreement for its subsidiary"
    assert tidy_case(sentence) == sentence


def test_the_body_wins_when_the_subject_is_only_a_label():
    h = make_headline(
        "Announcement under Regulation 30 (LODR)-Credit Rating",
        "CARE Ratings has reaffirmed AA+ on the company's bank loans. The rationale is attached.",
    )
    assert h == "CARE Ratings has reaffirmed AA+ on the company's bank loans."


def test_the_subject_wins_when_it_is_specific():
    h = make_headline(
        "Unaudited Financial Results For The Quarter And Half Year Ended September 30, 2026",
        "Financial results for the quarter and half year ended September 30, 2026 are attached",
    )
    assert h.startswith("Unaudited Financial Results for the Quarter and Half Year Ended")


def test_a_body_that_only_says_see_the_file_is_ignored():
    assert make_headline("Announcement under Regulation 30 (LODR)-Press Release / Media Release", "Please refer the enclosed file") == (
        "Press Release / Media Release"
    )


def test_the_nse_lead_in_is_stripped_from_the_body():
    h = make_headline("Updates", "Balaxi Pharmaceuticals Limited has informed the Exchange regarding Progress of the Company's Plant at Jadcherla")
    assert h == "Progress of the Company's Plant at Jadcherla"


def test_doubled_apostrophes_from_the_exchange_are_fixed():
    assert first_sentence("Company executives will attend the Institutional Investors'' Meeting") == (
        "Company executives will attend the Institutional Investors' Meeting"
    )


def test_an_abbreviation_does_not_end_the_sentence():
    # A real HDFC Bank headline was cut to "Re-appointment of Mr."
    assert first_sentence("Re-appointment of Mr. Rao as Managing Director. Effective from 1 April.") == (
        "Re-appointment of Mr. Rao as Managing Director."
    )


def test_a_single_letter_initial_does_not_end_the_sentence_either():
    assert first_sentence("Re-appointment of Mr. V. Vaidyanathan as Managing Director. Effective 1 April.") == (
        "Re-appointment of Mr. V. Vaidyanathan as Managing Director."
    )


def test_the_exchanges_question_mark_rupee_sign_is_repaired():
    assert "₹10/-" in first_sentence("Acquisition of 38,222 equity shares of face value ?10/- each")
    assert first_sentence("Why? Because we said so") == "Why?"  # a real question mark is left alone


def test_a_body_that_points_at_an_annexure_is_ignored():
    assert make_headline("Announcement under Regulation 30 (LODR)-Change in Management", "As per annexure enclosed") == (
        "Change in Management"
    )


def test_a_subject_that_is_only_boilerplate_gives_way_to_the_body():
    subject = "Disclosure under Regulation 30 of the SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015"
    assert make_headline(subject, "Re-appointment of Mr. Rao as CFO") == "Re-appointment of Mr. Rao as CFO"


def test_long_headlines_are_cut_at_a_word_boundary_with_an_ellipsis():
    h = make_headline("x", "word " * 80)
    assert len(h) <= 141 and h.endswith("…") and not h[:-1].endswith(" ")


def test_a_headline_is_never_empty():
    assert make_headline("", "") == "Filing"


# ---------- results de-duplication ----------
def result_item(item_id, symbol, ts, raw_category="Result", category="results"):
    return {"id": item_id, "symbol": symbol, "category": category, "published_at": ts, "raw_category": raw_category}


def test_a_results_filing_posted_twice_becomes_one_item_preferring_the_result_label():
    out = dedupe_results(
        [
            result_item("outcome", "RELIANCE", "2026-10-30T19:38:00+05:30", raw_category="Board Meeting"),
            result_item("result", "RELIANCE", "2026-10-30T19:42:00+05:30"),
        ]
    )
    assert [i["id"] for i in out] == ["result"] and out[0]["merged"] == 1


def test_if_there_is_no_result_labelled_row_the_first_one_is_kept():
    out = dedupe_results(
        [
            result_item("later", "X", "2026-10-30T20:00:00+05:30", raw_category="Board Meeting"),
            result_item("first", "X", "2026-10-30T19:00:00+05:30", raw_category="Board Meeting"),
        ]
    )
    assert [i["id"] for i in out] == ["first"]


def test_results_a_quarter_apart_are_both_kept():
    out = dedupe_results(
        [result_item("q2", "X", "2026-10-30T19:00:00+05:30"), result_item("q1", "X", "2026-07-30T19:00:00+05:30")]
    )
    assert [i["id"] for i in out] == ["q2", "q1"] and all(i["merged"] == 0 for i in out)


def test_other_companies_and_other_categories_are_untouched():
    other = result_item("n", "X", "2026-10-30T19:30:00+05:30", raw_category="Company Update", category="press_release")
    out = dedupe_results(
        [
            result_item("a", "X", "2026-10-30T19:00:00+05:30"),
            result_item("b", "Y", "2026-10-30T19:10:00+05:30"),
            other,
        ]
    )
    assert {i["id"] for i in out} == {"a", "b", "n"}
    assert "merged" not in next(i for i in out if i["id"] == "n")


def test_the_output_is_newest_first():
    out = dedupe_results(
        [result_item("old", "X", "2026-07-01T10:00:00+05:30"), result_item("new", "Y", "2026-11-01T10:00:00+05:30")]
    )
    assert [i["id"] for i in out] == ["new", "old"]


# ---------- the item the pipeline writes ----------
def test_a_results_filing_becomes_a_high_priority_item_with_its_reason():
    item = announcement_item(RESULTS, symbol="RELIANCE", company="Reliance Industries Ltd")
    assert item["category"] == "results" and item["card_type"] == "results"
    assert item["priority"] == 88 and item["routine"] is False and item["default_alert"] is True
    assert item["why"] == "Quarterly results are the most material filing"
    assert item["rule"] == "bse:Result/Financial Results"
    assert item["headline"].startswith("Unaudited Financial Results")
    assert item["url"].endswith(".pdf") and item["raw_category"] == "Result"


def test_transcripts_are_routine_wherever_they_were_filed():
    for row in (TRANSCRIPT, BAJAJ_TRANSCRIPT):
        item = announcement_item(row, symbol="X", company="X Ltd")
        assert item["category"] == "earnings_call" and item["routine"] is True


def test_every_item_carries_what_the_app_needs_to_rank_filter_and_explain_it():
    keys = {
        "id", "symbol", "company", "source", "published_at", "category", "category_label", "card_type", "priority",
        "routine", "default_alert", "why", "tone", "headline", "rule", "subject", "body", "raw_category",
        "raw_subcategory", "url", "size_kb",
    }
    for row in ROWS:
        assert set(announcement_item(row, symbol="X", company="X Ltd")) == keys
