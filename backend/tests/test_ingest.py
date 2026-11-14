"""Finding and reading a company's transcripts and annual report: discovery, labels, the cache, and every way it can go wrong.
No network: the exchanges and the downloader are fakes, and the PDFs are built here."""
from datetime import date, datetime

import pytest

from app.core.cache import Cache
from app.core.timeutil import IST
from app.pull import ingest as ig
from app.sources.models import Announcement, Listing
from tests.pdfs import make_plain_pdf, make_transcript_pdf

TODAY = date(2026, 11, 15)
LISTING = Listing("ACME", "Acme Ltd", "INE000000001", "500325", "123")
NSE_ONLY = Listing("ACME", "Acme Ltd", "INE000000001", None, None)
BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"


def ann(name, day, *, subject="Transcript of the earnings call", body="", subcategory="Earnings Call Transcript", category="Company Update", size=500_000, source="bse", ext=".pdf"):
    return Announcement(
        source, name, "Acme Ltd", "500325", category, subcategory, subject, body,
        datetime(day.year, day.month, day.day, 10, 0, tzinfo=IST), f"{BASE}{name}{ext}", size,
    )


def page_text(label):
    return f"{label}\nManagement: we will commission the new plant by Q3 FY27 and we are targeting capacity of 500 MW in the coming year, which is well on track.\n" * 3


def pdfs_for(urls_to_pages):
    return {url: make_transcript_pdf(pages) for url, pages in urls_to_pages.items()}


class Sources(ig.IngestSources):
    """Real IngestSources with everything fake, and a count of downloads."""


def sources(announcements, files, *, listing=LISTING, cache=None, bse_error=None, nse_error=None):
    downloads = []

    def pdf(url):
        downloads.append(url)
        if url not in files:
            raise ConnectionError("not found")
        return files[url]

    def bse_fetch(code, start, end):
        if bse_error:
            raise bse_error
        return list(announcements)

    def nse_fetch(symbol, start, end):
        if nse_error:
            raise nse_error
        return list(announcements)

    s = ig.IngestSources(resolve=lambda sym: listing, bse_announcements=bse_fetch, nse_announcements=nse_fetch, pdf=pdf, cache=cache, today=lambda: TODAY)
    s.downloads = downloads
    return s


# ---------------------------------------------------------------------------------------------- labels
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Q1 FY27 Earnings Conference Call", "Q1 FY27"),
        ("RIL Q2 FY2026 - 2027 Media & Analyst Meet Transcript", "Q2 FY27"),
        ("Q3 FY 2026-27 results call", "Q3 FY27"),
        ("Q4FY26 earnings call", "Q4 FY26"),
        ("Transcript of the call on results for the quarter ended June 30, 2026", "Q1 FY27"),
        ("Transcript of the analyst meet", None),
    ],
)
def test_the_quarter_a_call_is_about_is_read_from_its_own_words(text, expected):
    assert ig.quarter_from_text(text) == expected


@pytest.mark.parametrize(
    "day, before",
    [(date(2026, 1, 27), date(2025, 12, 31)), (date(2026, 5, 29), date(2026, 3, 31)), (date(2026, 7, 1), date(2026, 6, 30)), (date(2026, 6, 30), date(2026, 3, 31)), (date(2027, 1, 2), date(2026, 12, 31))],
)
def test_a_call_is_about_the_quarter_that_had_just_ended(day, before):
    assert ig.quarter_end_before(day) == before


@pytest.mark.parametrize(
    "text, expected",
    [
        ("transcript of the investor conference held on Tuesday, 27th January 2026", None),  # the day of a call is not a quarter-end
        ("Find enclosed the transcript of the call held on 29th May 2026", None),
        ("call on the results for the quarter ended June 30, 2026", "Q1 FY27"),
        ("results for the quarter ended 27 January 2026", None),  # not a quarter-end, so not a quarter
    ],
)
def test_a_date_somewhere_in_the_text_is_not_mistaken_for_a_quarter(text, expected):
    assert ig.quarter_from_text(text) == expected


def test_real_asian_paints_calls_get_their_right_quarters_including_the_one_with_a_typo_in_the_filing():
    # Filed 2025-11-18, 2026-02-02, 2026-06-03, 2026-08-03 ("held on 29th June", really 29 July) and 2026-11-03. Before
    # this was fixed, the January call became "Q4" and the May call "Q1 FY27" and was then lost to the real Q1 call.
    cases = [
        (date(2025, 11, 18), "Transcript of the investor conference held on Wednesday, 12th November 2025 on the business and financial performance", "Q2 FY26"),
        (date(2026, 2, 2), "Please find enclosed the transcript of the investor conference held on Tuesday, 27th January 2026, with respect to", "Q3 FY26"),
        (date(2026, 6, 3), "Find enclosed the transcript of the investor conference held on 29th May 2026", "Q4 FY26"),
        (date(2026, 8, 3), "Please find enclosed the transcript of the investor conference held on Wednesday 29th June 2026, with respect to", "Q1 FY27"),
        (date(2026, 11, 3), "Find enclosed the transcript of the investor conference call held on 29th October 2026 on the performance", "Q2 FY27"),
    ]
    for filed, body, label in cases:
        assert ig.quarter_for(ann("x", filed, subject="Announcement under Regulation 30 (LODR)-Earnings Call Transcript", body=body)) == label


def test_an_explicit_label_in_the_text_wins_over_dates():
    assert ig.quarter_for(ann("x", date(2026, 8, 8), subject="Q2 FY2026 - 2027 Media & Analyst Meet Transcript", body="held on 30th October 2026")) == "Q2 FY27"


# ---------------------------------------------------------------------------------------------- picking
def test_the_last_four_quarters_are_picked_the_biggest_file_wins_and_only_pdfs_count():
    announcements = [
        ann("old", date(2025, 8, 5), subject="Q1 FY26 earnings call transcript"),  # five calls: the oldest falls away
        ann("q2", date(2025, 11, 4), subject="Q2 FY26 earnings call transcript"),
        ann("q3", date(2026, 2, 3), subject="Q3 FY26 earnings call transcript"),
        ann("q4-small", date(2026, 5, 9), subject="Q4 FY26 earnings call transcript", size=100_000),
        ann("q4-big", date(2026, 5, 10), subject="Q4 FY26 earnings call transcript", size=900_000),
        ann("q1", date(2026, 8, 8), subject="Q1 FY27 earnings call transcript"),
        ann("audio", date(2026, 8, 9), subject="Audio recording of the Q1 FY27 call", subcategory="Analyst / Investor Meet", ext=".mp3"),
        ann("results", date(2026, 8, 7), subject="Financial results", subcategory="Financial Results", category="Result"),
    ]
    calls, report = ig.pick(announcements)
    assert [(label, a.id) for label, a in calls] == [("Q2 FY26", "q2"), ("Q3 FY26", "q3"), ("Q4 FY26", "q4-big"), ("Q1 FY27", "q1")]
    assert report is None


def test_a_call_filed_under_investor_meet_is_found_by_the_word_transcript_and_the_latest_annual_report_wins():
    announcements = [
        ann("t", date(2026, 7, 25), subject="Transcript of the earnings call", subcategory="Analyst / Investor Meet"),
        ann("ar25", date(2025, 8, 20), subject="Annual Report 2024-25", subcategory="Reg. 34 (1) Annual Report", category="AGM/EGM"),
        ann("ar26", date(2026, 8, 18), subject="Annual Report 2025-26", subcategory="Reg. 34 (1) Annual Report", category="AGM/EGM"),
    ]
    calls, report = ig.pick(announcements)
    assert [a.id for _l, a in calls] == ["t"] and report.id == "ar26"


# ---------------------------------------------------------------------------------------------- reading it all
def standard_files():
    return {
        BASE + "q2.pdf": [page_text("Q2 call page one"), page_text("Q2 call page two")],
        BASE + "q3.pdf": [page_text("Q3 call page one"), page_text("Q3 call page two")],
        BASE + "ar.pdf": [page_text(f"Annual report page {n}") for n in range(1, 26)],
    }


def standard_announcements():
    return [
        ann("q3", date(2026, 2, 3), subject="Q3 FY26 earnings call transcript"),
        ann("q2", date(2025, 11, 4), subject="Q2 FY26 earnings call transcript"),
        ann("ar", date(2026, 8, 18), subject="Annual Report 2025-26", subcategory="Reg. 34 (1) Annual Report", category="AGM/EGM", size=3_000_000),
    ]


def test_the_documents_are_read_in_order_oldest_call_first_and_the_annual_report_last():
    s = sources(standard_announcements(), pdfs_for(standard_files()))
    steps = []
    corpus = ig.ingest("ACME", s, progress=steps.append)
    assert [(d.id, d.kind, d.period, d.date) for d in corpus.documents] == [
        ("d1", "transcript", "Q2 FY26", "2025-11-04"), ("d2", "transcript", "Q3 FY26", "2026-02-03"), ("d3", "annual_report", "FY26", "2026-08-18"),
    ]
    assert [len(d.pages) for d in corpus.documents] == [2, 2, 25]
    assert [d.title for d in corpus.documents] == ["Q2 FY26 earnings call transcript", "Q3 FY26 earnings call transcript", "Annual report FY26"]  # a report filed in August 2026 is FY26
    assert "Q2 call page one" in corpus.documents[0].pages[0] and len(corpus.documents[0].sha256) == 64
    assert corpus.name == "Acme Ltd" and steps[0] == "Finding the company" and any("annual report" in m.lower() for m in steps)
    assert any("Only 2 concall transcript" in w for w in corpus.warnings)


def test_a_document_is_downloaded_once_and_the_next_ingest_reads_it_from_the_cache():
    cache = Cache(":memory:")
    first = sources(standard_announcements(), pdfs_for(standard_files()), cache=cache)
    ig.ingest("ACME", first)
    assert len(first.downloads) == 3
    second = sources(standard_announcements(), {}, cache=cache)  # nothing can be downloaded now
    corpus = ig.ingest("ACME", second)
    assert second.downloads == [] and [d.id for d in corpus.documents] == ["d1", "d2", "d3"]


def test_what_goes_wrong_with_one_document_is_a_warning_and_the_rest_are_still_read():
    files = pdfs_for(standard_files())
    files[BASE + "q3.pdf"] = make_plain_pdf(" ")  # a scan: no text layer
    corpus = ig.ingest("ACME", sources(standard_announcements(), files))
    assert [d.period for d in corpus.documents] == ["Q2 FY26", "FY26"]
    assert any("scan with no text layer" in w for w in corpus.warnings)
    del files[BASE + "q2.pdf"]  # now a download failure as well
    corpus = ig.ingest("ACME", sources(standard_announcements(), files))
    assert [d.period for d in corpus.documents] == ["FY26"] and any("could not be downloaded" in w and "ConnectionError" in w for w in corpus.warnings)


def test_an_annual_report_over_the_size_limit_is_not_downloaded():
    announcements = standard_announcements()
    announcements[2] = ann("ar", date(2026, 8, 18), subject="Annual Report", subcategory="Reg. 34 (1) Annual Report", category="AGM/EGM", size=40 * 1024 * 1024)
    s = sources(announcements, pdfs_for(standard_files()))
    corpus = ig.ingest("ACME", s)
    assert BASE + "ar.pdf" not in s.downloads and any("larger than the 25 MB limit" in w for w in corpus.warnings)


def test_a_company_with_no_annual_report_says_so():
    corpus = ig.ingest("ACME", sources(standard_announcements()[:2], pdfs_for(standard_files())))
    assert any("No annual report" in w for w in corpus.warnings) and all(d.kind == "transcript" for d in corpus.documents)


# ---------------------------------------------------------------------------------------------- nothing to read
def test_an_unknown_company_is_reported_not_crashed_on():
    s = sources([], {}, listing=None)
    with pytest.raises(ig.NoDocuments, match="not on NSE's list"):
        ig.ingest("NOSUCH", s)


def test_a_company_that_filed_no_transcript_or_report_says_so():
    s = sources([ann("res", date(2026, 8, 7), subject="Financial results", subcategory="Financial Results", category="Result")], {})
    with pytest.raises(ig.NoDocuments, match="No concall transcripts or annual report"):
        ig.ingest("ACME", s)


def test_when_every_document_is_unreadable_the_reasons_are_given():
    s = sources(standard_announcements(), {})  # nothing downloads
    with pytest.raises(ig.NoDocuments, match="none could be read") as caught:
        ig.ingest("ACME", s)
    assert "could not be downloaded" in caught.value.reason


def test_when_bse_is_down_nse_is_tried_and_when_both_are_down_the_reason_is_plain():
    files = pdfs_for(standard_files())
    corpus = ig.ingest("ACME", sources(standard_announcements(), files, bse_error=ConnectionError("down")))
    assert any("BSE announcements could not be fetched" in w for w in corpus.warnings) and corpus.documents
    with pytest.raises(ig.NoDocuments, match="Neither exchange could be reached"):
        ig.ingest("ACME", sources([], {}, bse_error=ConnectionError("x"), nse_error=TimeoutError("y")))


def test_a_company_bse_does_not_list_goes_straight_to_nse():
    def boom(*_a, **_k):
        raise AssertionError("BSE must not be called for an NSE-only company")

    s = sources(standard_announcements(), pdfs_for(standard_files()), listing=NSE_ONLY)
    s.bse_announcements = boom
    assert ig.ingest("ACME", s).documents


# ---------------------------------------------------------------------------------------------- the annual report
def ar(name, day, size, subject="Annual Report", subcategory="Reg. 34 (1) Annual Report", category="AGM/EGM"):
    return ann(name, day, subject=subject, subcategory=subcategory, category=category, size=size)


def test_the_report_is_the_biggest_filing_of_the_latest_cycle_not_the_covering_letter():
    # Real Asian Paints, 12 June 2026: the 26 MB report, the same file as an AGM notice, and a 2 MB letter listed last.
    filings = [
        ar("report", date(2026, 6, 12), 26_278_926),
        ar("letter", date(2026, 6, 12), 2_467_639, subject="Letter to shareholders in relation to Integrated Annual Report", subcategory="General"),
        ar("last-year", date(2025, 6, 10), 30_000_000),
    ]
    assert ig.pick_report(filings).id == "report"
    assert ig.pick_report([]) is None


def test_a_report_too_big_for_the_download_limit_is_said_so_and_the_small_letter_is_not_used_instead():
    announcements = [ar("report", date(2026, 6, 12), 26_278_926), ar("letter", date(2026, 6, 12), 2_467_639, subject="Letter about the Annual Report", subcategory="General")]
    s = sources(standard_announcements()[:2] + announcements, pdfs_for(standard_files()))
    corpus = ig.ingest("ACME", s)
    assert any("larger than the 25 MB limit" in w for w in corpus.warnings) and all(d.kind == "transcript" for d in corpus.documents)
    assert BASE + "letter.pdf" not in s.downloads


def test_a_two_page_notice_filed_as_the_report_is_not_used_as_one():
    files = pdfs_for(standard_files())
    files[BASE + "ar.pdf"] = make_transcript_pdf([page_text("Notice that the annual report is on our website"), page_text("with a link")])
    corpus = ig.ingest("ACME", sources(standard_announcements(), files))
    assert all(d.kind == "transcript" for d in corpus.documents) and any("only 2 pages long" in w for w in corpus.warnings)


def test_the_warning_about_too_few_calls_reads_naturally():
    corpus = ig.ingest("ACME", sources(standard_announcements()[1:], {BASE + "q2.pdf": make_transcript_pdf([page_text("Q2"), page_text("Q2 b")]), BASE + "ar.pdf": make_transcript_pdf([page_text(f"p{n}") for n in range(1, 26)])}))
    assert any(w.startswith("Only 1 concall transcript was found") for w in corpus.warnings)
