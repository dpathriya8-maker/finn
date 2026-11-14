"""Attaching the figures card to a company's results filings: ranking, caching, and what happens when it fails."""
from app.core.cache import Cache
from app.push import cards
from app.push import results_card as rc
from tests.pdfs import make_pdf, make_plain_pdf

URL = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/r1.pdf"
SUBJECT = "Results for the quarter ended 30 September 2026"


def item(n=1, *, url=URL, card_type="results", published="2026-11-14T09:00:00+05:30"):
    return {
        "id": f"bse:{n}", "published_at": published, "card_type": card_type, "url": url, "priority": 88, "tone": "neutral",
        "why": "Quarterly results are the most material filing", "headline": SUBJECT, "subject": SUBJECT, "body": "",
    }


class Downloads:
    """A stand-in for the downloader that counts how often it is asked."""

    def __init__(self, content=None, error=None):
        self.content, self.error, self.calls = content if content is not None else make_pdf(), error, []

    def __call__(self, url):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.content


def attach(items, pdf, **kwargs):
    return cards.attach_results_cards(items, yahoo=kwargs.pop("yahoo", []), pdf=pdf, **kwargs)


def test_a_results_filing_gets_a_card_and_its_numbers_decide_the_headline():
    it = item()
    counts = attach([it], Downloads())
    assert it["card"]["status"] == "ok" and counts["ok"] == 1
    assert it["tone"] == "good" and it["priority"] == 88  # good news is not pushed up
    assert it["headline"] == "Q2 FY27 results: profit up 43% from a year ago; revenue up 25%"
    assert it["why"] == "Quarterly results are the most material filing"


def test_weaker_numbers_rank_higher_and_say_why():
    bad, watch = item(1), item(2, url=URL.replace("r1", "r2"))
    attach([bad], Downloads(make_pdf(fiddle=lambda t: t["Profit after tax"].__setitem__(0, 80.0))))  # profit 24% below last year
    attach([watch], Downloads(make_pdf(fiddle=lambda t: t["Profit after tax"].__setitem__(0, 95.0))))  # 9% below
    assert (bad["tone"], bad["priority"]) == ("bad", 95) and (watch["tone"], watch["priority"]) == ("watch", 91)
    assert bad["why"].startswith("Weaker than a year ago, so it ranks higher. Quarterly results")
    assert watch["why"].startswith("Softer than a year ago")
    assert bad["headline"] == "Q2 FY27 results: profit down 24% from a year ago; revenue up 25%"


def test_the_rank_never_goes_past_100():
    it = item()
    it["priority"] = 98
    attach([it], Downloads(make_pdf(fiddle=lambda t: t["Profit after tax"].__setitem__(0, 80.0))))
    assert it["priority"] == 100


def test_only_results_filings_with_a_link_are_looked_at():
    other, no_link = item(1, card_type="one_liner"), item(2, url=None)
    downloads = Downloads()
    assert attach([other, no_link], downloads) == {"ok": 0, "partial": 0, "failed": 0, "cached": 0, "reused": 0}
    assert downloads.calls == [] and "card" not in other and "card" not in no_link


def test_only_the_newest_results_filings_of_a_company_are_read():
    items = [item(n, url=URL.replace("r1", f"r{n}"), published=f"2026-11-0{n}T09:00:00+05:30") for n in (1, 2, 3)]
    downloads = Downloads()
    attach(items, downloads)
    assert sorted(i["id"] for i in items if "card" in i) == ["bse:2", "bse:3"] and len(downloads.calls) == cards.MAX_PER_COMPANY


def test_what_was_read_is_kept_so_a_filing_is_downloaded_once():
    cache, downloads = Cache(":memory:"), Downloads()
    first, second = item(), item()
    assert attach([first], downloads, cache=cache)["cached"] == 0
    counts = attach([second], downloads, cache=cache)
    assert counts["cached"] == 1 and len(downloads.calls) == 1
    assert second["card"] == first["card"]


def test_the_cross_check_is_redone_every_run_because_yahoo_publishes_later():
    cache, downloads = Cache(":memory:"), Downloads()
    early, later = item(), item()
    attach([early], downloads, cache=cache, yahoo=[])
    assert early["card"]["check"]["status"] == "unavailable"
    yahoo = [{"period_end": "2026-09-30", "revenue_cr": 1000.0, "pbt_cr": 200.0, "net_income_cr": 150.0}]
    attach([later], downloads, cache=cache, yahoo=yahoo)
    assert later["card"]["check"]["status"] == "ok" and len(downloads.calls) == 1  # re-checked without a second download


def test_a_failed_download_becomes_a_card_that_says_so_and_is_not_remembered():
    cache, it = Cache(":memory:"), item()
    down = Downloads(error=ConnectionError("reset by peer"))
    assert attach([it], down, cache=cache)["failed"] == 1
    assert it["card"]["status"] == "failed" and "could not be downloaded" in it["card"]["reason"] and "ConnectionError" in it["card"]["reason"]
    assert "reset by peer" not in it["card"]["reason"]  # the reason is for readers, not a stack trace
    assert (it["tone"], it["priority"]) == ("neutral", 88)
    assert len(cache) == 0  # a network blip must not be remembered as the filing's answer
    again = item()
    attach([again], Downloads(), cache=cache)
    assert again["card"]["status"] == "ok"


def test_a_good_card_from_the_last_run_survives_a_failed_download():
    first = item()
    attach([first], Downloads())
    now = item()
    counts = attach([now], Downloads(error=TimeoutError()), previous={now["id"]: first["card"]})
    assert counts["reused"] == 1 and now["card"] == first["card"] and now["tone"] == "good"


def test_an_earlier_failure_is_not_reused_it_is_tried_again():
    now = item()
    counts = attach([now], Downloads(error=TimeoutError()), previous={now["id"]: {"status": "failed", "reason": "x"}})
    assert counts["failed"] == 1 and counts["reused"] == 0


def test_a_pdf_without_a_results_statement_gets_an_honest_failed_card_and_is_remembered():
    cache, downloads = Cache(":memory:"), Downloads(make_plain_pdf())
    it = item()
    assert attach([it], downloads, cache=cache)["failed"] == 1
    assert it["card"]["status"] == "failed" and "No quarterly results statement" in it["card"]["reason"]
    attach([item()], downloads, cache=cache)
    assert len(downloads.calls) == 1  # the same file gives the same answer, so it is not fetched again


def test_a_filing_that_is_not_a_pdf_at_all_does_not_stop_anything():
    it = item()
    attach([it], Downloads(b"definitely not a pdf"))
    assert it["card"]["status"] == "failed" and "could not be read" in it["card"]["reason"]


def test_an_item_that_already_has_a_card_is_left_alone_so_it_is_never_ranked_twice():
    it = item()
    attach([it], Downloads(make_pdf(fiddle=lambda t: t["Profit after tax"].__setitem__(0, 80.0))))
    ranked, why = it["priority"], it["why"]
    downloads = Downloads()
    attach([it], downloads)
    assert (it["priority"], it["why"]) == (ranked, why) and downloads.calls == []


def test_a_stored_reading_from_an_older_layout_is_not_trusted():
    cache = Cache(":memory:")
    cache.set(cards.cache_key(URL), {"extraction": {"basis": 1}})  # missing everything else
    it = item()
    attach([it], Downloads(), cache=cache)
    assert it["card"]["status"] == "failed" and "stored reading" in it["card"]["reason"]


def test_the_cache_is_keyed_by_the_extractor_version(monkeypatch):
    cache, downloads = Cache(":memory:"), Downloads()
    attach([item()], downloads, cache=cache)
    monkeypatch.setattr(rc, "EXTRACTOR_VERSION", "next")  # a better extractor must re-read, not trust the old answer
    attach([item()], downloads, cache=cache)
    assert len(downloads.calls) == 2


# ---------------------------------------------------------------------------------------------- management cards
import json
from pathlib import Path

from tests.pdfs import make_plain_pdf

MGMT_URL = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/m1.pdf"
FIXTURES = Path(__file__).parent / "fixtures" / "management"


def management_item(n=1, *, headline="Change in Management", url=MGMT_URL, published="2026-11-14T09:00:00+05:30", priority=85, tone="neutral"):
    return {
        "id": f"bse:m{n}", "source": "bse", "company": "Apollo Hospitals Enterprise Ltd", "category": "management_change", "card_type": "management",
        "raw_category": "Company Update", "raw_subcategory": "Change in Management", "subject": "Announcement under Regulation 30 (LODR)-Change in Management",
        "body": "As per annexure enclosed", "headline": headline, "published_at": published, "url": url, "priority": priority, "tone": tone,
        "why": "Leadership changes move stocks", "routine": False, "rule": "bse:Company Update/Change in Management",
    }


def appointment_pdf(text="Appointment of Ms. Priya Nair as Chief Financial Officer"):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate([f"Sub: {text}", "The Board approved the appointment of Ms. Priya Nair (DIN: 01234567) as Chief Financial Officer", "with effect from 1st December 2026."]):
        page.insert_text((60, 72 + 16 * i), line, fontsize=10)
    return doc.tobytes()


def attach_management(items, pdf, **kwargs):
    return cards.attach_management_cards(items, pdf=pdf, **kwargs)


def test_a_management_filing_gets_a_card_with_its_facts_and_a_headline_that_names_the_person():
    it = management_item(headline="Change in Management")
    counts = attach_management([it], Downloads(appointment_pdf()))
    card = it["card"]
    assert counts["ok"] == 1 and card["type"] == "management" and card["status"] == "ok"
    assert card["people"][0]["name"] == "Ms. Priya Nair" and card["people"][0]["effective"]["date"] == "2026-12-01"
    assert card["source"]["url"] == MGMT_URL
    assert it["headline"] == "Ms. Priya Nair appointed as Chief Financial Officer, from 1 Dec"  # the vague headline is replaced


def test_a_headline_that_already_names_the_person_is_kept():
    it = management_item(headline="Appointment of Ms. Priya Nair as Chief Financial Officer")
    attach_management([it], Downloads(appointment_pdf()))
    assert it["headline"] == "Appointment of Ms. Priya Nair as Chief Financial Officer"


def test_a_key_person_leaving_ranks_higher_than_the_vague_headline_said():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(["Sub: Intimation under Regulation 30", "Mr. Rahul Verma has tendered his resignation as Chief Financial Officer, w.e.f. close of business hours on 30th November, 2026."]):
        page.insert_text((40, 72 + 16 * i), line, fontsize=8)
    it = management_item(headline="Change in Management", priority=85, tone="neutral")
    attach_management([it], Downloads(doc.tobytes()))
    assert it["card"]["kind"] == "resignation"
    assert (it["tone"], it["priority"]) == ("bad", 97) and it["why"].startswith("A key person is leaving")  # 85 + 12


def test_a_card_never_lowers_a_filings_rank_or_moves_it_to_another_category():
    it = management_item(headline="Appointment of Ms. Priya Nair as Chief Financial Officer", priority=99)
    attach_management([it], Downloads(appointment_pdf()))
    assert it["priority"] == 99 and it["category"] == "management_change"


def test_a_management_filing_is_read_once_and_remembered():
    cache, downloads = Cache(":memory:"), Downloads(appointment_pdf())
    attach_management([management_item()], downloads, cache=cache)
    second = management_item()
    assert attach_management([second], downloads, cache=cache)["cached"] == 1 and len(downloads.calls) == 1
    assert second["card"]["status"] == "ok"


def test_the_same_file_under_a_different_headline_is_read_again_because_it_may_announce_something_else():
    cache, downloads = Cache(":memory:"), Downloads(appointment_pdf())
    attach_management([management_item(headline="Change in Management")], downloads, cache=cache)
    attach_management([management_item(headline="Resignation of Mr. Rahul Verma as Chief Financial Officer")], downloads, cache=cache)
    assert len(downloads.calls) == 2


def test_a_failed_management_download_is_a_failed_card_and_a_good_earlier_card_survives():
    failed = management_item()
    assert attach_management([failed], Downloads(error=TimeoutError()))["failed"] == 1
    assert failed["card"]["status"] == "failed" and failed["card"]["type"] == "management" and "TimeoutError" in failed["card"]["reason"]
    first = management_item()
    attach_management([first], Downloads(appointment_pdf()))
    again = management_item()
    assert attach_management([again], Downloads(error=TimeoutError()), previous={again["id"]: first["card"]})["reused"] == 1
    assert again["card"] == first["card"]


def test_a_results_card_is_not_reused_for_a_management_filing_or_the_other_way_round():
    it = management_item()
    results_card = {"type": "results", "status": "ok"}
    assert attach_management([it], Downloads(error=TimeoutError()), previous={it["id"]: results_card})["failed"] == 1


def test_a_pdf_with_no_text_gets_an_honest_failed_card():
    it = management_item()
    attach_management([it], Downloads(make_plain_pdf(" ")))
    assert it["card"]["status"] in ("failed", "partial")  # nothing to read: no facts are invented
    assert it["card"].get("people", []) == []


def test_two_announcements_in_one_file_are_downloaded_once():
    downloads = Downloads(appointment_pdf())
    once = cards.PdfOnce(downloads)
    assert once(MGMT_URL) is once(MGMT_URL) and len(downloads.calls) == 1
    once("https://www.bseindia.com/xml-data/corpfiling/AttachLive/other.pdf")
    assert len(downloads.calls) == 2


def test_the_management_items_are_capped_per_company():
    items = [management_item(n, url=MGMT_URL.replace("m1", f"m{n}"), published=f"2026-11-0{n}T09:00:00+05:30") for n in range(1, 6)]
    downloads = Downloads(appointment_pdf())
    attach_management(items, downloads)
    assert sum("card" in i for i in items) == cards.MAX_MANAGEMENT_PER_COMPANY
