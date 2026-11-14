"""Text clean-up, the verbatim check, chunking, the rule-based statements and retrieval, on three real transcripts
(Reliance, Kaynes, Bajaj Finance) and on small synthetic pages for the edge cases."""
import json
from pathlib import Path

import pytest

from app.pull import chunk as ck
from app.pull.retrieve import Index, tokens
from app.pull.text import normalise, quote_is_in, strip_repeated_lines, tidy_blocks

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"
NAMES = ["RELIANCE", "KAYNES", "BAJFINANCE"]


def raw_pages(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["pages"]


def prepared(name):
    pages = strip_repeated_lines(raw_pages(name))
    return pages, ck.chunk_pages("d1", pages)


# ---------------------------------------------------------------------------------------------- the verbatim check
@pytest.mark.parametrize(
    "quote, page, ok",
    [
        ("revenue grew 20% in the quarter", "We saw that revenue grew\n20% in the quarter, which was good.", True),  # a line break is not a difference
        ("year-on-year growth of 24%", "a year-on-\nyear growth of 24% in EBITDA", True),  # a word broken across lines
        ("it’s our target of INR500 crores", "It's our target of INR500 crores this year", False),  # case counts
        ("it’s our target of INR500 crores", "so it's our target of INR500 crores this year", True),  # curly and straight apostrophes are the same
        ("target of INR500 crores", "a target of INR600 crores for the year", False),  # a changed number is not the same quote
        ("we will commission the plant", "we shall commission the plant", False),  # a changed word is not the same quote
        ("margins stay—above 20%—through the year", "margins stay-above 20%-through the year", True),  # dashes
        ("ﬁnancial services grew strongly", "financial services grew strongly this year", True),  # a ligature
        ("short", "short quote here", False),  # too short to count as evidence
    ],
)
def test_a_quote_must_be_word_for_word_but_forgives_what_a_pdf_does_to_text(quote, page, ok):
    assert quote_is_in(quote, page) is ok


def test_normalise_collapses_whitespace_and_joins_hyphenated_line_breaks():
    assert normalise("a  b\n c d") == "a b c d" and normalise("year-on-\nyear") == "year-on-year"


def test_repeated_headers_and_page_numbers_are_removed_but_content_stays():
    pages = [f"Acme Ltd\nAugust 08, 2026\nPage {n} of 9\nreal content of page {n}\n{n}" for n in range(1, 8)]
    cleaned = strip_repeated_lines(pages)
    assert cleaned[2] == "real content of page 3"


# ---------------------------------------------------------------------------------------------- chunks
def test_a_chunk_never_crosses_a_page_and_is_a_literal_part_of_it():
    for name in NAMES:
        pages, chunks = prepared(name)
        assert len(chunks) > 40
        for c in chunks:
            assert 1 <= c.page <= len(pages) and len(c.text) <= ck.MAX_CHARS * 1.3
            assert quote_is_in(c.text[:200], pages[c.page - 1]), f"{name} p{c.page}: chunk text is not in its own page"


def test_no_chunk_carries_a_page_header_or_number():
    for name in NAMES:
        _pages, chunks = prepared(name)
        assert not [c for c in chunks if "Page 3 of 19" in c.text or "Page 12 of" in c.text]


def test_turns_split_at_speaker_labels_and_the_moderator_is_marked():
    page = "Moderator:\nLadies and gentlemen, welcome to the call and please stay on the line for the opening remarks today.\nRajeev Jain:\nThank you. We will grow 25% next year, and we are targeting credit costs below 2% for the full year of FY27."
    chunks = ck.chunk_pages("d1", [page])
    assert [c.moderator for c in chunks] == [True, False]
    assert chunks[1].text.startswith("Thank you. We will grow 25%")  # the label is not part of the text


def test_a_label_in_the_middle_of_a_block_still_starts_a_new_turn():
    # Real transcripts put the next speaker's label on the line after the previous speaker's last line, with no blank line.
    page = "we remain comfortable with the outlook for the full year and the quarters ahead of us\nRajeev Jain:\nthank you for the question, we will deliver 26% growth next year as guided to the street earlier"
    chunks = ck.chunk_pages("d1", [page])
    assert len(chunks) == 2 and "Rajeev" not in chunks[0].text


@pytest.mark.parametrize("junk", ["Corporate ID No: L65910MH1987PLC042961", "MANAGEMENT: MR. RAJEEV JAIN - VICE CHAIRMAN", "Page 1 of 19", "Subject: Transcript of the earnings call held on", "Telephone No: 022 61939000"])
def test_cover_page_fields_are_not_speakers(junk):
    assert ck._label(junk) is None


def test_a_long_paragraph_is_cut_at_sentence_ends():
    sentence = "This sentence says something fairly long about the business and its plans. "
    chunks = ck.chunk_pages("d1", [sentence * 40])
    assert len(chunks) > 1 and all(c.text.endswith(".") for c in chunks) and all(len(c.text) <= ck.MAX_CHARS for c in chunks)


# ---------------------------------------------------------------------------------------------- forward-looking statements
def test_every_statement_in_every_real_transcript_is_a_verbatim_span_of_the_page_it_cites():
    total = 0
    for name in NAMES:
        pages, chunks = prepared(name)
        statements = ck.forward_statements(chunks, limit=12)
        assert len(statements) >= 3, name
        for s in statements:
            total += 1
            assert quote_is_in(s.text, pages[s.page - 1]), f"{name} p{s.page}: {s.text[:80]}"
            assert "?" not in s.text and ck.MIN_SENTENCE <= len(s.text) <= ck.MAX_SENTENCE
    assert total >= 15


def test_kaynes_capex_commitment_is_found_on_its_page_and_a_forecast_by_someone_else_is_not():
    _pages, kaynes = prepared("KAYNES")
    found = {s.page: s.text for s in ck.forward_statements(kaynes, limit=12)}
    assert any("capex for this year is about INR300 crores for OSAT" in t for t in found.values())
    _pages, reliance = prepared("RELIANCE")
    assert not [s for s in ck.forward_statements(reliance, limit=12) if "IEA" in s.text]  # an agency's projection is not management's commitment


def test_a_question_or_the_moderator_or_a_disclaimer_is_not_a_statement():
    chunks = [
        ck.Chunk("d1", 1, "Could you tell us whether you will target 25% growth by FY27 for the lending book going forward?"),
        ck.Chunk("d1", 1, "We will target 25% growth by FY27 across the lending book as we said earlier this year.", moderator=True),
        ck.Chunk("d1", 2, "This presentation contains forward-looking statements and we expect results of 25% by FY27 with no assurance of this."),
        ck.Chunk("d1", 3, "We will target 25% growth by FY27 across the lending book as we said earlier this year."),
    ]
    assert [s.page for s in ck.forward_statements(chunks)] == [3]


def test_a_sentence_with_a_forward_verb_but_no_number_or_date_is_not_a_statement():
    chunk = ck.Chunk("d1", 1, "We will continue to work hard for all of our customers and partners in the coming period ahead of us.")
    assert ck.forward_statements([chunk]) == []


# ---------------------------------------------------------------------------------------------- retrieval
def test_the_index_finds_the_page_that_talks_about_the_question():
    pages, chunks = prepared("KAYNES")
    index = Index(chunks)
    top = index.search("what is the capex plan for OSAT and PCB this year", k=3)
    assert top and top[0].chunk.page == 16 and top[0].coverage >= 0.5
    assert quote_is_in(top[0].chunk.text[:150], pages[15])


def test_a_question_about_something_the_documents_never_mention_finds_nothing_useful():
    _pages, chunks = prepared("KAYNES")
    hits = Index(chunks).search("lithium battery gigafactory subsidy in Gujarat", k=5)
    assert not [h for h in hits if h.coverage >= 0.5]


def test_the_document_filter_and_an_empty_index_behave():
    a, b = ck.Chunk("d1", 1, "capex of INR300 crores planned for the year ahead"), ck.Chunk("d2", 4, "capex of INR900 crores planned for the year ahead")
    index = Index([a, b])
    assert [h.chunk.doc for h in index.search("capex plan", docs={"d2"})] == ["d2"]
    assert Index([]).search("anything at all") == [] and index.search("the of and") == []


def test_tokens_fold_plurals_and_drop_filler():
    assert tokens("What are the capacities and the plans?") == ["capacity", "plan"]
    assert tidy_blocks("a\nb\n\nc") == [["a", "b"], ["c"]]


@pytest.mark.parametrize(
    "analyst",
    [
        "Sir, my question is on the number of deliveries that we are expecting and the guidance of 20% by FY27.",
        "And secondly, I just want to understand this pipeline that you mentioned of INR900 billion orders over the next 2 years.",
        "I understand over the next six months you are still looking at 4 to 5% but when you frame your plans for FY27 on mix.",
        "Given what you said earlier about 25% growth by FY27 for the lending book, will the target hold for the full year.",
    ],
)
def test_an_analysts_remarks_are_not_taken_for_a_commitment(analyst):
    assert ck.forward_statements([ck.Chunk("d1", 1, analyst)]) == []


@pytest.mark.parametrize(
    "management",
    [
        "We expect to keep our operating margin above 20% through FY27 and we will update you every quarter on this.",
        "We plan to invest around INR12,000 crores in these projects by 2030.",
    ],
)
def test_management_speaking_for_the_company_still_counts_even_when_it_says_you(management):
    assert [s.text for s in ck.forward_statements([ck.Chunk("d1", 1, management)])] == [management]
