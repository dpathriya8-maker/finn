"""The management-change card: facts read from the filing's own words. Real filings (page texts cut from four of them),
synthetic ones for the cases no real sample covers, and the rules that keep a wrong person's profile off a card."""
import json
from datetime import date
from pathlib import Path

import pytest

from app.push import mgmt_card as mc
from tests.pdfs import make_plain_pdf

FIXTURES = Path(__file__).parent / "fixtures" / "management"


def real(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    pages = {int(n): t for n, t in data["pages"].items()}
    return mc.build_card(pages, headline=data["headline"], subject=data["subject"], company=data["company"], source_url="https://example.test/f.pdf")


def card(text, headline, company="Acme Ltd", subject=""):
    return mc.build_card({1: text}, headline=headline, subject=subject, company=company)


# ---------------------------------------------------------------------------------------------- real filings
def test_hdfc_reappointment_has_person_role_date_term_and_the_filings_own_profile():
    c = real("HDFCBANK_2026-11-13")
    assert c["status"] == "ok" and c["type"] == "management" and (c["kind"], c["direction"]) == ("re-appointment", "in")
    p = c["people"][0]
    assert p["name"] == "Mr. V. Srinivasa Rangan" and p["din"] == "00030248"
    assert p["role"] == "Whole-time Director (designated as Executive Director)"
    assert p["effective"] == {"date": "2026-11-23", "text": "November 23, 2026"} and p["term"] == "1 year" and p["page"] == 1
    profile = p["profile"]
    assert profile["page"] == 4 and profile["source"] == "filing"
    assert profile["text"].startswith("Mr. V. Srinivasa Rangan, aged sixty-six (66) years, is the Executive Director of the Bank and heads the")
    assert profile["text"].endswith("functions of the Bank. He holds a Bachelor’s degree in Commerce from University of Delhi and is an Associate of the Institute of Chartered Accountants of India (ICAI).")
    assert c["source"] == {"url": "https://example.test/f.pdf", "pages": [1]}
    assert mc.headline_for(c) == "Mr. V. Srinivasa Rangan re-appointed as Whole-time Director (designated as Executive Director), from 23 Nov"


def test_a_headline_cut_short_with_an_ellipsis_gets_its_role_from_the_filings_own_sentence():
    # The announcement's headline is truncated ("... as the Whole-time Director (designated as Executive…").
    c = real("HDFCBANK_2026-11-12")
    assert c["status"] == "ok" and c["people"][0]["role"] == "Whole-time Director (designated as Executive Director)"
    assert c["people"][0]["profile"] is None  # this filing has no profile section, and none is invented


def test_tata_steel_retirement_keeps_the_commas_in_the_role_and_ignores_the_results_in_the_same_pdf():
    # The PDF is a board-outcome letter whose other 22 pages are the results statements.
    c = real("TATASTEEL_2026-11-07")
    p = c["people"][0]
    assert (c["kind"], c["direction"]) == ("retirement", "out") and p["name"] == "Mr. Noel Naval Tata" and p["din"] == "00024713"
    assert p["role"] == "Non-Executive, Non-Independent Director and Vice-Chairman of the Board"
    assert p["effective"] == {"date": "2026-11-11", "text": "November 11, 2026"}
    assert p["profile"] is None  # nobody joins, so there is no "incoming person" to describe
    assert len(c["people"]) == 1


def test_a_scanned_filing_with_a_vague_headline_is_read_from_its_own_sentence():
    # Apollo's headline is just "Change in Management"; the filing is a scan with scrambled reading order.
    c = real("APOLLOHOSP_2026-11-04")
    p = c["people"][0]
    assert (c["kind"], c["direction"]) == ("cessation", "out")
    assert p["name"] == "Dr. Madhu Sasidhar" and p["role"] == "President & CEO - Hospitals Division"
    assert p["effective"] == {"date": "2026-11-14", "text": "November 14, 2026"}
    assert mc.headline_for(c) == "Dr. Madhu Sasidhar to cease as President & CEO - Hospitals Division, from 14 Nov"


# ---------------------------------------------------------------------------------------------- an appointment, with a profile
APPOINTMENT = """Sub: Appointment of Ms. Priya Nair as Chief Financial Officer
The Board of Directors has approved the appointment of Ms. Priya Nair (DIN: 01234567) as Chief Financial Officer
and Key Managerial Personnel of the Company with effect from 1st December 2026, for a term of five (5) years.
Annexure I
Brief profile (in case of appointment)
Ms. Priya Nair is a Chartered Accountant with over 22 years of experience in finance at Hindustan Unilever and Tata Motors.
She was most recently Vice President - Finance at Tata Motors. She holds a bachelor's degree in commerce from Mumbai University.
She also serves on the audit committee of a subsidiary. Her last role was in treasury.
Disclosure of relationships between directors: Not applicable
"""


def test_a_new_appointment_shows_who_joins_from_when_and_what_the_filing_says_about_them():
    c = card(APPOINTMENT, "Appointment of Ms. Priya Nair as Chief Financial Officer")
    p = c["people"][0]
    assert (c["kind"], c["direction"]) == ("appointment", "in") and p["role"] == "Chief Financial Officer"
    assert p["name"] == "Ms. Priya Nair" and p["din"] == "01234567"
    assert p["effective"] == {"date": "2026-12-01", "text": "1st December 2026"} and p["term"] == "5 years"
    # Verbatim, whole sentences, three at most.
    assert p["profile"]["text"] == (
        "Ms. Priya Nair is a Chartered Accountant with over 22 years of experience in finance at Hindustan Unilever and Tata Motors. "
        "She was most recently Vice President - Finance at Tata Motors. She holds a bachelor's degree in commerce from Mumbai University."
    )
    assert mc.headline_for(c) == "Ms. Priya Nair appointed as Chief Financial Officer, from 1 Dec"


def test_every_word_of_a_shown_profile_is_in_the_filing():
    c = card(APPOINTMENT, "Appointment of Ms. Priya Nair as Chief Financial Officer")
    shown = c["people"][0]["profile"]["text"]
    assert shown in mc.squash(APPOINTMENT)  # a literal span, not a paraphrase


def test_one_sentence_longer_than_the_limit_is_cut_at_a_word_and_marked():
    words = " ".join(f"word{i}" for i in range(400))
    c = card(f"Appointment of Mr. Ravi Rao as Director\nBrief profile\nMr. Ravi Rao has {words}.\n", "Appointment of Mr. Ravi Rao as Director")
    shown = c["people"][0]["profile"]["text"]
    assert shown.endswith("…") and len(shown) <= mc.PROFILE_MAX_CHARS + 1 and shown.startswith("Mr. Ravi Rao has word0 word1")


def test_a_profile_is_cut_at_a_sentence_and_never_runs_past_the_length_limit():
    long_profile = " ".join(f"Sentence number {i} says something fairly long about this person's career in banking." for i in range(12))
    text = f"Appointment of Mr. Ravi Rao as Director\nBrief profile\nMr. Ravi Rao. {long_profile}\n"
    c = card(text, "Appointment of Mr. Ravi Rao as Director")
    shown = c["people"][0]["profile"]["text"]
    assert shown.endswith(".") and len(shown) <= mc.PROFILE_MAX_CHARS and len(mc._sentences(shown)) <= mc.PROFILE_MAX_SENTENCES


@pytest.mark.parametrize("filler", ["Not applicable", "As provided in Annexure II.", "Refer to the enclosed document for the details of the director."])
def test_a_profile_row_that_only_points_elsewhere_is_not_shown(filler):
    text = f"Appointment of Mr. Ravi Rao as Director with effect from 1.12.2026\nBrief profile (in case of appointment)\n{filler}\nDisclosure of relationships between directors: none\n"
    assert card(text, "Appointment of Mr. Ravi Rao as Director")["people"][0]["profile"] is None


# ---------------------------------------------------------------------------------------------- two people in one filing
TWO = """The Board approved the appointment of Mr. Alpha Rao as an Independent Director and the appointment of Ms. Beta Sen as a Non-Executive Director.
Profile of Mr. Alpha Rao
Mr. Alpha Rao is a retired civil servant with thirty years of experience in public finance, and sat on three government committees on taxation.
Profile of Ms. Beta Sen
Ms. Beta Sen is the founder of a logistics company and has built supply chains across eleven countries for global retailers over two decades.
"""


def test_each_appointee_gets_their_own_profile_and_never_the_others():
    c = card(TWO, "Appointment of Directors")
    by_name = {p["name"]: p for p in c["people"]}
    assert set(by_name) == {"Mr. Alpha Rao", "Ms. Beta Sen"}
    assert by_name["Mr. Alpha Rao"]["role"] == "Independent Director" and by_name["Ms. Beta Sen"]["role"] == "Non-Executive Director"
    assert by_name["Mr. Alpha Rao"]["profile"]["text"].startswith("Mr. Alpha Rao is a retired civil servant")
    assert by_name["Ms. Beta Sen"]["profile"]["text"].startswith("Ms. Beta Sen is the founder of a logistics company")


# ---------------------------------------------------------------------------------------------- exits
def test_a_resignation_names_the_person_the_role_and_the_last_day():
    text = "Sub: Resignation of Mr. Rahul Verma as Chief Financial Officer\nMr. Rahul Verma has tendered his resignation as Chief Financial Officer, w.e.f. close of business hours on 30th November, 2026."
    c = card(text, "Resignation of Mr. Rahul Verma as Chief Financial Officer")
    p = c["people"][0]
    assert (c["kind"], c["direction"]) == ("resignation", "out") and p["role"] == "Chief Financial Officer"
    assert p["effective"] == {"date": "2026-11-30", "text": "30th November, 2026"}
    assert p["profile"] is None
    assert mc.headline_for(c) == "Mr. Rahul Verma resigns as Chief Financial Officer, from 30 Nov"


def test_a_vague_headline_is_read_from_the_sentence_that_states_the_event():
    text = "Intimation under Regulation 30.\nMr. A. Kumar has resigned from the position of Chief Executive Officer w.e.f. 15.12.2026 due to personal reasons."
    c = card(text, "Change in Management")
    assert (c["kind"], c["people"][0]["name"], c["people"][0]["role"]) == ("resignation", "Mr. A. Kumar", "Chief Executive Officer")
    assert c["people"][0]["effective"]["date"] == "2026-12-15"


def test_a_death_is_reported_as_such():
    c = card("Sub: Demise of Mr. Sunil Mehta as Chairman of the Company\nWith deep regret we inform you...", "Demise of Mr. Sunil Mehta as Chairman of the Company")
    assert c["kind"] == "death" and c["people"][0]["role"] == "Chairman"  # "of the Company" is the company, not part of the role


# ---------------------------------------------------------------------------------------------- when nothing can be said
def test_when_nobody_can_be_named_the_card_says_so_and_claims_nothing_more():
    c = card("This is to inform you about a change in key managerial personnel as per annexure.", "Change in Management")
    assert c["status"] == "partial" and c["people"] == [] and c["kind"] == "change"
    assert "could not be read" in c["warnings"][0]
    assert mc.headline_for(c) is None


def test_a_filing_with_no_text_layer_is_not_guessed_at():
    c = mc.build_card({1: "  \n", 2: ""}, headline="Change in Management")
    assert c["status"] == "failed" and "no readable text" in c["reason"]


def test_bytes_that_are_not_a_pdf_do_not_stop_the_run():
    reading = mc.read_filing(b"not a pdf", "Change in Management", "", "Acme Ltd")
    assert reading["card"]["status"] == "failed" and "could not be read" in reading["card"]["reason"]


def test_a_real_pdf_goes_from_bytes_to_a_card():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Sub: Appointment of Ms. Priya Nair as Chief Financial Officer", fontsize=10)
    page.insert_text((72, 90), "The Board approved her appointment w.e.f. 1st December 2026.", fontsize=10)
    reading = mc.read_filing(doc.tobytes(), "Appointment of Ms. Priya Nair as Chief Financial Officer", "", "Acme Ltd")
    assert reading["card"]["status"] == "ok" and reading["card"]["people"][0]["name"] == "Ms. Priya Nair"
    # A filing that says nothing more than the headline still shows what the headline says, and nothing else.
    bare = mc.read_filing(make_plain_pdf("Nothing about management here"), "Appointment of Mr. X Y as CEO", "", "Acme")["card"]["people"][0]
    assert (bare["name"], bare["role"], bare["effective"], bare["profile"], bare["din"]) == ("Mr. X Y", "CEO", None, None, None)


# ---------------------------------------------------------------------------------------------- the small rules
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Re-appointment of Mr. X", ("re-appointment", "in")),
        ("Reappointment of Mr. X", ("re-appointment", "in")),
        ("Appointment of a Director", ("appointment", "in")),
        ("Resignation of the CFO", ("resignation", "out")),
        ("Cessation of Mr. X", ("cessation", "out")),
        ("Demise of the Chairman", ("death", "out")),
        ("Retirement by rotation", ("retirement", "out")),
        ("Quarterly results", None),
    ],
)
def test_the_kind_of_change_from_its_words_with_reappointment_tested_first(text, expected):
    assert mc.kind_of(text) == expected


@pytest.mark.parametrize(
    "text, day",
    [
        ("w.e.f. 1st December 2026", date(2026, 12, 1)),
        ("with effect from 01.12.2026", date(2026, 12, 1)),
        ("effective from the closure of business hours on November 14, 2026", date(2026, 11, 14)),
        ("effective close of business hours on 11th November, 2026", date(2026, 11, 11)),
        ("w.e.f. December 1, 2026", date(2026, 12, 1)),
    ],
)
def test_the_effective_date_in_the_ways_filings_write_it(text, day):
    found = mc.find_effective(f"The Board approved the change {text} and the rest.")
    assert found is not None and found[1] == day


def test_a_date_that_is_not_attached_to_the_word_effective_is_not_the_effective_date():
    assert mc.find_effective("Our letter dated September 12, 2026 refers to the meeting held on November 12, 2026.") is None


@pytest.mark.parametrize(
    "text, expected",
    [("for a period of 1 (one) year", "1 year"), ("for a term of five (5) years", "5 years"), ("for a period of 3 months", "3 months"), ("for a period of two years", "two years"), ("nothing here", None)],
)
def test_the_term(text, expected):
    assert mc.find_term(text) == expected


def test_a_role_is_tidied_of_the_company_name_and_the_filings_typos():
    tidy = mc._tidy_role
    assert tidy("Whole-time Director(designated as Executive Director) of HDFC Bank Limited", "HDFC Bank Ltd") == "Whole-time Director (designated as Executive Director)"
    assert tidy("Chairman of the Company", "Acme Ltd") == "Chairman"
    assert tidy("Non-Executive Director and as Vice-Chairman of the Board", "Tata Steel Ltd") == "Non-Executive Director and Vice-Chairman of the Board"
    assert tidy("Head of Sales, India", "Acme Ltd") == "Head of Sales, India"  # "of Sales" is part of the role


def test_a_headline_for_a_card_that_could_not_name_anyone_is_not_made_up():
    assert mc.headline_for({"status": "ok", "people": [{"kind": "appointment", "name": "Mr. A B", "role": "", "effective": None}]}) is None
    assert mc.headline_for({"status": "failed", "reason": "x"}) is None


@pytest.mark.parametrize(
    "role, ok",
    [
        ("Chief Financial Officer", True),
        ("Chairman of the Board of Directors", True),
        ("Head of Systems Analysts, India", True),  # "Systems" ends in "ms" but is not an honorific
        ("Non-Executive, Non-Independent Director and Vice-Chairman of the Board", True),
        ("Chief Financial Officer The Board of Directors has approved the appointment of Ms", False),  # a run-on into the next sentence
        ("Director and Mr. Rao as Chairman", False),  # another person inside a role
        ("x" * 111, False),
    ],
)
def test_only_something_that_reads_like_a_role_is_shown_as_one(role, ok):
    assert mc._plausible(role) is ok


def test_a_run_on_headline_and_sentence_do_not_hide_the_din(  # the filing's "Sub:" line runs into its next sentence once whitespace is squashed
):
    c = card(APPOINTMENT, "Appointment of Ms. Priya Nair as Chief Financial Officer")
    assert c["people"][0]["din"] == "01234567" and c["people"][0]["page"] == 1
