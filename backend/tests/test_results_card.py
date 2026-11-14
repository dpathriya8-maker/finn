"""The results-card extractor. Real filings (word positions cut from seven of them), synthetic PDFs, and the safety rules."""
import json
from datetime import date
from pathlib import Path

import pytest

from app.push import results_card as rc
from tests.pdfs import make_pdf, make_plain_pdf

FIXTURES = Path(__file__).parent / "fixtures" / "results"


# ---------------------------------------------------------------------------------------------- helpers
def load(symbol):
    return json.loads((FIXTURES / f"{symbol}.json").read_text(encoding="utf-8"))


def card_for(symbol):
    fx = load(symbol)
    pages = {fx["page"]: [rc.Word(*w) for w in fx["words"]]}
    texts = {int(k): v for k, v in fx["texts"].items()}
    ex = rc.extract_statement(pages, texts)
    assert ex is not None, f"{symbol}: no statement found"
    period_end = ex.current or rc.period_end_from_text(fx["hint"])
    return ex, rc.build_card(ex, period_end=period_end, yahoo=fx["yahoo"], source_url="https://example.test/x.pdf")


def metric(card, key):
    return next((m for m in card["metrics"] if m["key"] == key), None)


def figures(card, key):
    m = metric(card, key)
    return (m["current"], m["previous"], m["year_ago"])


def row(label, *tokens, page=1):
    return rc.Row(label, [rc.Cell(t, rc.parse_number(t)) if t else None for t in tokens], page)


# ---------------------------------------------------------------------------------------------- numbers
@pytest.mark.parametrize(
    "token, expected",
    [
        ("332,861", 332861.0),  # Reliance, crore
        ("6,672.71", 6672.71),
        ("(17,539)", -17539.0),  # brackets mean negative
        ("-1,902.63", -1902.63),
        ("1,41,887.37", 141887.37),  # Indian lakh grouping, as Tata Steel prints it
        ("1,45,468", 145468.0),
        ("17.369.35", 17369.35),  # Bajaj Finance: a comma printed as a dot
        ("1.679.03", 1679.03),
        ("10241.16", 10241.16),  # ITC prints no separators
        ("0.50", 0.5),
        ("2260", 2260.0),
    ],
)
def test_figures_the_way_indian_filings_print_them(token, expected):
    assert rc.parse_number(token) == expected


@pytest.mark.parametrize("token", ["-", "–", "", "nil", "30.09.2026", "4,2so.n", "J,19.236", "5,)01", "12.5%", "abc", "1,23"])
def test_dashes_dates_and_garbled_text_are_not_numbers(token):
    assert rc.parse_number(token) is None  # dropped, never guessed


# ---------------------------------------------------------------------------------------------- real filings
def test_reliance_consolidated_quarter():
    ex, card = card_for("RELIANCE")
    assert card["status"] == "ok" and card["basis"] == "consolidated" and card["unit_printed"] == "crore"
    assert (card["period"]["label"], card["period"]["current"]) == ("Q2 FY27", "2026-09-30")
    assert card["period"]["previous"] == "2026-06-30" and card["period"]["year_ago"] == "2025-09-30"
    assert figures(card, "revenue") == (332861.0, 311850.0, 258898.0)  # "Revenue from Operations", not Total Income
    assert figures(card, "pbt") == (38613.0, 30630.0, 29124.0)
    assert figures(card, "pat") == (29250.0, 23001.0, 22146.0)
    revenue = metric(card, "revenue")
    assert revenue["printed"]["tokens"] == ["332,861", "311,850", "258,898"] and revenue["printed"]["page"] == 10
    assert (revenue["qoq_pct"], revenue["yoy_pct"]) == (6.7, 28.6)
    assert metric(card, "ebitda")["current"] == 56616.0 and "Computed" in metric(card, "ebitda")["derived"]
    assert card["check"]["status"] == "ok" and card["tone"] == "good" and card["warnings"] == []
    assert ex.order_read  # read from the header dates, despite Reliance's own typo "Seo'25"


def test_kaynes_converts_rupees_million_to_crore_and_reports_a_fall():
    _, card = card_for("KAYNES")
    assert card["unit_printed"] == "million" and card["basis"] == "consolidated"
    assert figures(card, "revenue")[0] == pytest.approx(952.5, abs=0.01)  # 9,525.15 million is Rs 952.5 crore
    assert metric(card, "pbt")["yoy_pct"] == -56.3 and metric(card, "pat")["yoy_pct"] == -65.6
    assert card["tone"] == "bad" and "down 66%" in card["tone_reason"]
    assert card["check"]["status"] == "unavailable" and "not published" in card["check"]["note"]  # Yahoo lags a fresh filing


def test_bajaj_finance_is_a_lender_so_no_ebitda_and_no_revenue_check():
    _, card = card_for("BAJFINANCE")
    assert metric(card, "ebitda") is None
    assert figures(card, "pbt") == (8537.2, 8149.0, 6608.13)
    assert card["check"]["status"] == "ok" and [d["metric"] for d in card["check"]["details"]] == ["pbt"]


def test_tata_steel_rotated_pages_are_read_by_how_they_look():
    fx = load("TATASTEEL")
    assert fx["rotation"] == 270  # its statements are turned sideways in the PDF
    _, card = card_for("TATASTEEL")
    assert card["status"] == "ok" and card["basis"] == "consolidated"
    assert figures(card, "revenue") == (65436.24, 60794.29, 58689.29)
    assert figures(card, "pbt")[0] == 5455.15
    assert card["check"]["status"] == "ok"


def test_itc_prints_the_year_ago_column_second_so_the_order_is_read_not_assumed():
    ex, card = card_for("ITC")
    assert ex.order_read
    # Columns in the PDF are September 2026, September 2025, June 2026. The excise-duty jump after Feb 2026 only makes sense this way.
    assert figures(card, "revenue") == (30578.4, 29523.3, 21255.86)
    assert figures(card, "pbt") == (5694.62, 5860.85, 6978.68)
    assert (metric(card, "revenue")["qoq_pct"], metric(card, "revenue")["yoy_pct"]) == (3.6, 43.9)
    assert metric(card, "pbt")["yoy_pct"] == -18.4 and card["tone"] == "watch"
    # Yahoo's revenue is net of excise duty, and the card still matches it once that is taken into account.
    assert card["check"]["status"] == "ok"


def test_a_scanned_filing_shows_only_what_yahoo_confirms():
    ex, card = card_for("BHARTIARTL")
    assert ex.scanned
    assert card["status"] == "partial" and [m["key"] for m in card["metrics"]] == ["pbt"]
    assert card["verification"].startswith("Scanned filing")
    assert figures(card, "pbt") == (15428.0, 13772.8, None)  # the year-ago figure could not be confirmed, so it is withheld
    assert any("Revenue could not be read" in w for w in card["warnings"])


def test_a_scan_that_cannot_be_confirmed_is_refused_not_guessed():
    ex, card = card_for("APOLLOHOSP")
    assert ex.scanned and card["status"] == "failed"
    assert "scan" in card["reason"] and "Open the filing" in card["reason"]


# ---------------------------------------------------------------------------------------------- synthetic PDFs
def build(pdf, yahoo=()):
    return rc.results_card_from_pdf(pdf, hint_text="Results for the quarter ended 30 September 2026", yahoo=list(yahoo), source_url="u")


def test_a_synthetic_pdf_goes_the_whole_way_from_bytes_to_a_card():
    card = build(make_pdf())
    assert card["status"] == "ok" and card["basis"] == "consolidated" and card["unit_printed"] == "crore"
    assert figures(card, "revenue") == (1000.0, 900.0, 800.0)
    assert (metric(card, "revenue")["qoq_pct"], metric(card, "revenue")["yoy_pct"]) == (11.1, 25.0)
    assert figures(card, "pbt") == (200.0, 145.0, 140.0) and figures(card, "pat") == (150.0, 109.0, 105.0)
    assert card["margins"]["pbt"] == {"current": 20.0, "year_ago": 17.5}
    assert card["source"]["pages"] == [1] and card["check"]["status"] == "unavailable"


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_a_rotated_page_gives_the_same_card(rotation):
    assert build(make_pdf(rotation=rotation))["metrics"] == build(make_pdf())["metrics"]


def test_the_quarter_order_follows_the_header_dates():
    # The columns hold 1000, 900, 800 and the header says: September 2026, September 2025, June 2026 (the ITC order).
    # So 900 is the year-ago quarter and 800 is the preceding one, the reverse of the usual order.
    card = build(make_pdf(dates=("30.09.2026", "30.09.2025", "30.06.2026")))
    assert figures(card, "revenue") == (1000.0, 800.0, 900.0)  # (current, preceding quarter, year ago)
    assert metric(card, "revenue")["qoq_pct"] == 25.0 and metric(card, "revenue")["yoy_pct"] == 11.1


def test_lakh_and_million_figures_are_converted_to_crore():
    assert figures(build(make_pdf(unit="Rs. in lakhs")), "revenue")[0] == 10.0
    assert figures(build(make_pdf(unit="Rs. in million")), "revenue")[0] == 100.0


def test_a_misread_digit_that_breaks_total_income_removes_that_column_only():
    def break_previous_quarter(table):
        table["Total income"][1] = 999.0  # revenue 900 + other 45 is 945, so the preceding-quarter column is not to be trusted

    card = build(make_pdf(fiddle=break_previous_quarter))
    assert figures(card, "revenue") == (1000.0, None, 800.0)
    assert any("failed the check" in w for w in card["warnings"])


def test_a_broken_current_quarter_means_no_card_at_all():
    def break_current(table):
        table["Total income"][0] = 1.0

    assert build(make_pdf(fiddle=break_current))["status"] == "failed"


def test_a_pdf_with_no_results_statement_says_so():
    card = rc.results_card_from_pdf(make_plain_pdf(), hint_text="", yahoo=[], source_url=None)
    assert card["status"] == "failed" and "No quarterly results statement" in card["reason"]


def test_garbage_bytes_do_not_crash_the_pipeline():
    card = rc.results_card_from_pdf(b"not a pdf at all", hint_text="", yahoo=[], source_url=None)
    assert card["status"] == "failed" and "could not be read" in card["reason"]


# ---------------------------------------------------------------------------------------------- the maths
def test_percent_change_means_nothing_against_a_zero_or_negative_base():
    assert rc.pct_change(110, 100) == 10.0 and rc.pct_change(90, 100) == -10.0
    assert rc.pct_change(5, 0) is None and rc.pct_change(5, -3) is None and rc.pct_change(None, 3) is None
    assert rc.pct_change(0, 50) == -100.0


def test_a_swing_between_profit_and_loss_is_named_not_given_a_percentage():
    assert rc._swing(10, -5) == "turned profit" and rc._swing(-10, 5) == "turned loss"
    assert rc._swing(10, 5) is None and rc._swing(None, 5) is None


@pytest.mark.parametrize(
    "end, label",
    [(date(2026, 6, 30), "Q1 FY27"), (date(2026, 9, 30), "Q2 FY27"), (date(2026, 12, 31), "Q3 FY27"), (date(2027, 3, 31), "Q4 FY27"), (date(2026, 3, 31), "Q4 FY26")],
)
def test_indian_fiscal_quarters(end, label):
    assert rc.fiscal_label(end) == label


def test_shifting_by_months_respects_month_ends_and_leap_years():
    assert rc._shift_months(date(2026, 9, 30), -3) == date(2026, 6, 30)
    assert rc._shift_months(date(2026, 9, 30), -12) == date(2025, 9, 30)
    assert rc._shift_months(date(2026, 5, 31), -3) == date(2026, 2, 28)
    assert rc._shift_months(date(2028, 5, 31), -3) == date(2028, 2, 29)


@pytest.mark.parametrize(
    "text",
    ["30th September 2026", "30.09.2026", "30/09/2026", "September 30, 2026", "30-Sep-2026", "30 Sep'26", "30th Seo'26"],
)
def test_dates_as_filings_write_them(text):
    assert rc.parse_date(text) == date(2026, 9, 30)


def test_the_quarter_end_comes_from_the_filings_own_words():
    assert rc.period_end_from_text("Results for the Quarter and Half Year Ended 30 September 2026") == date(2026, 9, 30)
    assert rc.period_end_from_text("Financial results for the year ended March 31, 2026") == date(2026, 3, 31)


def test_the_last_date_in_a_header_cell_is_the_one_nearest_the_figures():
    assert rc.parse_date("ENDED 30TH SEPTEMBER 2026 30th June 2026", last=True) == date(2026, 6, 30)


# ---------------------------------------------------------------------------------------------- the safety rules
def test_total_income_must_equal_revenue_plus_other_income_or_the_column_is_dropped():
    revenue = row("Revenue from operations", "1,000.00", "900.00", "800.00")
    other = row("Other income", "50.00", "45.00", "40.00")
    assert rc._failed_columns(revenue, other, row("Total income", "1,050.00", "945.00", "840.00")) == set()
    assert rc._failed_columns(revenue, other, row("Total income", "1,050.00", "999.00", "840.00")) == {1}
    assert rc._failed_columns(revenue, other, row("Total income", "1,050.50", "945.00", "840.00")) == set()  # rounding is tolerated
    total = row("Total income", "1,050.00", "945.00", "840.00")
    assert rc._failed_columns(total, other, total) == set()  # when total income stands in for revenue there is nothing to compare


def test_a_scan_is_recognised_by_figures_stuck_in_its_labels():
    noisy = [row("(c) Finance costs 1,712 1,683 1,579 1,395 2,417"), row("(d) Other expenses 9,203 8,745 7.208 17,947"), row("Cost of goods 7,299 6,671 6,188 13,970")]
    clean = [row("Revenue from operations"), row("Finance costs"), row("Profit before tax (5+6)"), row("Notes 2 and 3 from 2026")]
    assert rc.looks_scanned(noisy) and not rc.looks_scanned(clean)
    assert not rc.looks_scanned(noisy[:2])  # two noisy rows are not enough to call a filing a scan
    assert not rc.looks_scanned([row("Note 10 712 683 579")] * 5)  # short numbers are note references, not stuck figures


def test_a_serial_number_column_is_not_mistaken_for_a_period():
    rows = [row("Revenue", "1", "28,317.67", "19,441.50", "26,943.23"), row("Other income", "2", "807.52", "899.47", "645.33"), row("Total income", "3", "29,125.19", "20,340.97", "27,588.56")]
    assert [r.cells[0].text for r in rc._drop_serial_columns(rows)] == ["28,317.67", "807.52", "29,125.19"]


def test_a_real_column_of_small_whole_numbers_is_left_alone():
    rows = [row("A", "12", "9", "7"), row("B", "5", "4", "3")]  # all whole numbers: nothing marks the first as a serial column
    assert [r.cells[0].text for r in rc._drop_serial_columns(rows)] == ["12", "5"]


def test_a_stray_fragment_after_the_figures_does_not_swallow_them_into_the_label():
    words = [rc.Word(10 + 60 * i, 0, 50 + 60 * i, 8, t) for i, t in enumerate(["Total", "income", "65,684.52", "61,026.97", "59,052.84", "2,32,"])]
    label, values = rc.split_row(words)
    assert [w.text for w in label] == ["Total", "income"] and [w.text for w in values] == ["65,684.52", "61,026.97", "59,052.84"]


def test_figures_printed_before_the_label_are_a_serial_number():
    words = [rc.Word(10, 0, 20, 8, "3"), rc.Word(40, 0, 90, 8, "Profit"), rc.Word(95, 0, 140, 8, "before"), rc.Word(200, 0, 250, 8, "1,270.17"), rc.Word(260, 0, 310, 8, "947.23"), rc.Word(320, 0, 370, 8, "405.55")]
    label, values = rc.split_row(words)
    assert [w.text for w in label] == ["Profit", "before"] and len(values) == 3


def test_the_unit_is_found_on_a_neighbouring_page_when_the_statement_page_does_not_say():
    texts = {9: "Statement with no unit stated", 10: "(Rs. in lakhs) notes", 5: "(Rs. in crore)"}
    assert rc.detect_unit(texts, [9]) == "lakh"
    assert rc.detect_unit({9: "nothing"}, [9]) is None


def test_consolidated_wins_over_standalone_and_continuation_pages_never_borrow_a_basis_from_afar():
    assert rc.detect_basis("STATEMENT OF UNAUDITED CONSOLIDATED FINANCIAL RESULTS") == "consolidated"
    assert rc.detect_basis("Standalone Statement of Profit and Loss ... consolidated entities") == "standalone"
    assert rc.detect_basis("Particulars Quarter ended") is None


# ---------------------------------------------------------------------------------------------- the cross-check
def check(current_pbt, yahoo_pbt, *, lender=False, revenue=1000.0, yahoo_revenue=1000.0, excise=None):
    ex = rc.Extraction(
        basis="consolidated", unit="crore", pages=[1], lender=lender,
        rows={"excise": row("Excise duty", f"{excise:,.2f}", "0", "0") if excise else None}, revenue_label="", dropped=[],
        scanned=False, order_read=True, current=date(2026, 9, 30), warnings=[],
    )
    card = {"metrics": [{"key": "revenue", "current": revenue}, {"key": "pbt", "current": current_pbt}]}
    yahoo = [{"period_end": "2026-09-30", "revenue_cr": yahoo_revenue, "pbt_cr": yahoo_pbt, "net_income_cr": None}]
    return rc.cross_check(card, yahoo, ex, date(2026, 9, 30))


def test_the_cross_check_passes_when_the_numbers_agree_and_flags_when_they_do_not():
    assert check(200.0, 200.0)["status"] == "ok"
    assert check(200.0, 198.0)["status"] == "ok"  # 1.0%: inside the 1.5% tolerance for profit
    bad = check(200.0, 150.0)
    assert bad["status"] == "differs" and "filing is the source of truth" in bad["note"]
    assert [d["ok"] for d in bad["details"]] == [True, False]


def test_a_lenders_revenue_is_not_compared_because_yahoo_defines_it_differently():
    result = check(200.0, 200.0, lender=True, revenue=2400.0, yahoo_revenue=1500.0)
    assert result["status"] == "ok" and [d["metric"] for d in result["details"]] == ["pbt"]


def test_revenue_may_match_yahoo_before_or_after_excise_duty():
    # ITC: the filing's revenue includes excise duty, Yahoo's does not, and the two agree once it is removed.
    assert check(200.0, 200.0, revenue=3000.0, yahoo_revenue=2000.0, excise=1000.0)["status"] == "ok"
    assert check(200.0, 200.0, revenue=3000.0, yahoo_revenue=2000.0)["status"] == "differs"


def test_the_cross_check_says_when_there_is_nothing_to_compare():
    ex = rc.Extraction("consolidated", "crore", [1], False, {}, "", [], False, True, None, [])
    assert rc.cross_check({"metrics": []}, [], ex, None)["status"] == "unavailable"
    assert "not published" in rc.cross_check({"metrics": []}, [{"period_end": "2026-06-30"}], ex, date(2026, 9, 30))["note"]


def test_a_scanned_filings_columns_survive_only_where_yahoo_confirms_them():
    pbt = row("Profit before tax", "100.00", "90.00", "80.00")
    ex = rc.Extraction("consolidated", "crore", [1], False, {"pbt": pbt}, "", [], True, False, None, [])
    yahoo = [{"period_end": "2026-09-30", "pbt_cr": 100.5}, {"period_end": "2026-06-30", "pbt_cr": 60.0}, {"period_end": "2025-09-30", "pbt_cr": 80.0}]
    assert rc.verified_columns(ex, yahoo, date(2026, 9, 30)) == {0, 2}  # the preceding quarter disagrees, so it is withheld
    assert rc.verified_columns(ex, [], date(2026, 9, 30)) == set()
    assert rc.verified_columns(ex, yahoo, None) == set()


# ---------------------------------------------------------------------------------------------- the tone
def metrics(pat_yoy, rev_yoy, swing=None, pat_key="pat"):
    return {pat_key: {"yoy_pct": pat_yoy, "yoy_swing": swing}, "revenue": {"yoy_pct": rev_yoy}}


@pytest.mark.parametrize(
    "pat_yoy, rev_yoy, swing, tone",
    [(-25.0, 5.0, None, "bad"), (-3.0, -4.0, None, "bad"), (-10.0, 5.0, None, "watch"), (2.0, -1.0, None, "watch"),
     (20.0, 8.0, None, "good"), (20.0, -2.0, None, "watch"), (5.0, 3.0, None, "neutral"), (None, 3.0, "turned loss", "bad"),
     (None, 3.0, "turned profit", "good"), (None, 3.0, None, "neutral")],
)
def test_the_tone_judges_direction_against_last_year_and_never_claims_a_beat_or_miss(pat_yoy, rev_yoy, swing, tone):
    got, reason = rc.tone_for(metrics(pat_yoy, rev_yoy, swing))
    assert got == tone
    assert "beat" not in reason.lower() and "miss" not in reason.lower()


def test_the_tone_reason_is_plain_language():
    assert rc.tone_for(metrics(-31.0, 4.0))[1] == "Profit down 31% from a year ago; revenue up 4%"
    assert rc.tone_for(metrics(12.0, None, pat_key="pbt"))[1] == "Pre-tax profit up 12% from a year ago"


# ---------------------------------------------------------------------------------------------- reading vs. card
@pytest.mark.parametrize("symbol", ["RELIANCE", "KAYNES", "BAJFINANCE", "TATASTEEL", "ITC", "BHARTIARTL", "APOLLOHOSP"])
def test_a_reading_survives_being_stored_and_gives_the_same_card(symbol):
    fx = load(symbol)
    pages = {fx["page"]: [rc.Word(*w) for w in fx["words"]]}
    ex = rc.extract_statement(pages, {int(k): v for k, v in fx["texts"].items()})
    stored = json.loads(json.dumps(rc.extraction_to_dict(ex)))  # through JSON, as the cache keeps it
    assert rc.extraction_from_dict(stored) == ex
    direct = rc.build_card(ex, period_end=ex.current or rc.period_end_from_text(fx["hint"]), yahoo=fx["yahoo"], source_url="u")
    rebuilt = rc.card_from_reading({"extraction": stored, "first_page_period": None}, hint_text=fx["hint"], yahoo=fx["yahoo"], source_url="u")
    assert rebuilt == direct


def test_a_reading_that_found_nothing_stays_failed_with_its_reason():
    assert rc.card_from_reading({"error": "boom"}, hint_text="", yahoo=[], source_url=None) == {"type": "results", "status": "failed", "reason": "boom", "extractor": rc.EXTRACTOR_VERSION}


def test_a_reading_in_a_layout_this_code_does_not_know_is_refused_not_guessed():
    card = rc.card_from_reading({"extraction": {"basis": 1}}, hint_text="", yahoo=[], source_url=None)
    assert card["status"] == "failed" and "stored reading" in card["reason"]


def test_the_date_on_the_first_page_is_the_last_resort_for_the_quarter():
    # A header whose dates cannot be read and a hint that names none: the PDF's own first page says the quarter.
    first_page = rc.read_pdf(make_pdf(dates=("-", "-", "-"), title="Results for the quarter ended 30 September 2026 consolidated")) 
    assert first_page["extraction"]["current"] is None
    card = rc.card_from_reading(first_page, hint_text="", yahoo=[], source_url=None)
    assert card["period"]["label"] == "Q2 FY27"


# ---------------------------------------------------------------------------------------------- a garbled profit row
def test_itcs_garbled_profit_row_is_completed_from_pbt_less_tax_and_says_so():
    ex, card = card_for("ITC")
    # In the PDF itself the figures of this row are damaged: "PROFIT FOR THE PERIOD (8-9) 10 4229.33 51B6.55 4508.79".
    assert ex.filled == [0, 2]
    assert figures(card, "pat") == (4229.33, 4508.79, 5186.55)
    pat = metric(card, "pat")
    assert pat["printed"]["label"] == "PROFIT FOR THE PERIOD" and pat["printed"]["tokens"] == [None, "4508.79", None]
    assert pat["derived"] == (
        "The filing's printed figure for this quarter and the year-ago quarter could not be read, so it is computed as "
        "profit before tax less tax expense. The same sum reproduces the printed figure for the preceding quarter."
    )
    assert (pat["qoq_pct"], pat["yoy_pct"]) == (-6.2, -18.5)
    assert card["tone_reason"] == "Profit down 18% from a year ago; revenue up 44%"


def test_a_missing_profit_figure_is_computed_only_where_the_sum_reproduces_the_printed_ones():
    pbt, tax = row("Profit before tax", "200.00", "145.00", "140.00"), row("Tax expense", "50.00", "36.00", "35.00")
    damaged = row("Profit for the period (8-9) 10 150.00 1O5.00", "", "109.00", "")
    filled, columns = rc._fill_profit(damaged, pbt, tax)
    assert columns == [0, 2] and [c.value for c in filled.cells[:3]] == [150.0, 109.0, 105.0] and filled.label == "Profit for the period"
    assert filled.cells[0].text == "" and filled.cells[1].text == "109.00"  # computed figures carry no printed token


@pytest.mark.parametrize(
    "profit, tax",
    [
        (("", "111.00", ""), ("50.00", "36.00", "35.00")),  # the printed figure (111) disagrees with 145 - 36, so the sum is not trusted
        (("", "", ""), ("50.00", "36.00", "35.00")),  # nothing printed to check the sum against
        (("150.00", "109.00", "105.00"), ("50.00", "36.00", "35.00")),  # nothing to fill
    ],
)
def test_the_profit_row_is_left_alone_when_the_sum_cannot_be_checked_or_is_not_needed(profit, tax):
    pbt = row("Profit before tax", "200.00", "145.00", "140.00")
    pat, tax_row = row("Profit for the period", *profit), row("Tax expense", *tax)
    assert rc._fill_profit(pat, pbt, tax_row) == (pat, [])


def test_without_a_tax_row_or_a_pbt_row_nothing_is_computed():
    pat = row("Profit for the period", "", "109.00", "")
    pbt, tax = row("Profit before tax", "200.00", "145.00", "140.00"), row("Tax expense", "50.00", "36.00", "35.00")
    assert rc._fill_profit(pat, pbt, None) == (pat, []) and rc._fill_profit(pat, None, tax) == (pat, []) and rc._fill_profit(None, pbt, tax) == (None, [])
