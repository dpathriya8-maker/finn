"""When a promise is due: the Indian fiscal calendar (FY27 = April 2026 to March 2027) and the loose ways people say it."""
from datetime import date

import pytest

from app.pull import periods as pe

CALL = date(2026, 8, 4)  # a Q1 FY27 call


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Q1 FY27", date(2026, 6, 30)),
        ("Q2 FY27", date(2026, 9, 30)),
        ("Q3 FY27", date(2026, 12, 31)),
        ("Q4 FY27", date(2027, 3, 31)),
        ("Q4FY26", date(2026, 3, 31)),
        ("q3 fy2027", date(2026, 12, 31)),
        ("Q2-FY27", date(2026, 9, 30)),
        ("H1 FY27", date(2026, 9, 30)),
        ("H2 FY27", date(2027, 3, 31)),
        ("second half of FY27", date(2027, 3, 31)),
        ("FY27", date(2027, 3, 31)),
        ("FY 2027", date(2027, 3, 31)),
        ("FY2026-27", date(2027, 3, 31)),
        ("FY26-27", date(2027, 3, 31)),
        ("Mar 2027", date(2027, 3, 31)),
        ("October 2026", date(2026, 10, 31)),
        ("Nov '26", date(2026, 11, 30)),
        ("CY2026", date(2026, 12, 31)),
        ("calendar 2027", date(2027, 12, 31)),
        ("by 2028", date(2028, 12, 31)),
    ],
)
def test_a_period_written_out_is_read_to_its_last_day(text, expected):
    assert pe.period_end(text, CALL) == expected


def test_the_latest_of_several_periods_is_the_deadline():
    assert pe.period_end("Q2 FY27 and Q3 FY27", CALL) == date(2026, 12, 31)
    assert pe.period_end("Oct 2026, Nov 2026", CALL) == date(2026, 11, 30)


@pytest.mark.parametrize(
    "text, call, expected",
    [
        ("Q2", date(2026, 8, 4), date(2026, 9, 30)),  # said in August: this fiscal year's Q2, still ahead
        ("Q1", date(2026, 5, 28), date(2026, 6, 30)),  # said in May on the Q4 call: Q1 of FY27, in progress
        ("Q4", date(2026, 2, 7), date(2026, 3, 31)),
        ("Q1", date(2026, 8, 4), date(2027, 6, 30)),  # Q1 FY27 is over by August: the next Q1
        ("second half", date(2026, 10, 30), date(2027, 3, 31)),
        ("first half", date(2026, 5, 4), date(2026, 9, 30)),
        ("H2", date(2026, 8, 4), date(2027, 3, 31)),
        ("this year", date(2026, 2, 7), date(2026, 3, 31)),  # a Q3 FY26 call: this fiscal year is FY26
        ("this year", date(2026, 8, 4), date(2027, 3, 31)),
        ("full year basis", date(2026, 2, 7), date(2026, 3, 31)),
        ("as we exit the year", date(2026, 2, 7), date(2026, 3, 31)),
        ("next year", date(2026, 8, 4), date(2028, 3, 31)),
        ("by March", date(2026, 2, 7), date(2026, 3, 31)),
        ("by March", date(2026, 10, 30), date(2027, 3, 31)),
        ("by October, November", date(2026, 8, 4), date(2026, 11, 30)),
        ("in the next 2 years", date(2026, 8, 4), date(2028, 8, 31)),
        ("over the next three years", date(2026, 8, 4), date(2029, 8, 31)),
        ("next quarter", date(2026, 2, 7), date(2026, 3, 31)),
    ],
)
def test_relative_terms_are_read_from_the_day_of_the_call(text, call, expected):
    assert pe.period_end(text, call) == expected


@pytest.mark.parametrize("text", [None, "", "none", "null", "not stated", "ongoing", "going forward", "soon", "in the market", "may be", "we may launch", "the 2025 crore plan is big"])
def test_no_period_means_none_and_ordinary_words_are_not_months(text):
    assert pe.period_end(text, CALL) is None


def test_relative_terms_without_a_call_date_are_not_guessed():
    assert pe.period_end("this year", None) is None and pe.period_end("by March", None) is None
    assert pe.period_end("Q3 FY27", None) == date(2026, 12, 31)  # a written-out period needs no anchor


def test_a_quarter_in_a_fiscal_year_is_not_also_read_as_the_year():
    assert pe.period_end("Q1 FY27", CALL) == date(2026, 6, 30)  # not 31 Mar 2027, which "FY27" alone would give


def test_label():
    assert pe.label(date(2027, 3, 31)) == "31 Mar 2027"


# The phrasings found in the real transcripts (Bajaj Finance, Asian Paints), said on the dates of those calls.
@pytest.mark.parametrize(
    "text, call, expected",
    [
        ("first half of this year", date(2026, 6, 3), date(2026, 9, 30)),  # Q4 FY26 call: the first half of FY27, not "H2"
        ("second half of this year", date(2026, 6, 3), date(2027, 3, 31)),
        ("Q3 of next year", date(2026, 8, 4), date(2027, 12, 31)),
        ("between Q2 and Q3 of FY'27", date(2026, 5, 4), date(2026, 12, 31)),
        ("in the 6 months' time", date(2026, 11, 3), date(2027, 5, 31)),
        ("within a year's time", date(2026, 11, 3), date(2027, 11, 30)),
        ("next 3 to 4 years' time", date(2026, 2, 7), date(2030, 2, 28)),
        ("over a period of next 15-odd months", date(2026, 2, 7), date(2027, 5, 31)),
        ("for November", date(2026, 11, 3), date(2026, 11, 30)),
        ("between April and May'26", date(2026, 2, 7), date(2026, 5, 31)),
        ("by September '26", date(2026, 5, 4), date(2026, 9, 30)),
        ("by September", date(2026, 2, 7), date(2026, 9, 30)),
        ("By year-end", date(2026, 8, 4), date(2027, 3, 31)),
        ("by Q3 or so", date(2026, 8, 4), date(2026, 12, 31)),
        ("on a full year basis", date(2026, 2, 7), date(2026, 3, 31)),  # said in February: that is FY26, which ends in March
        ("in the full year this year", date(2026, 8, 4), date(2027, 3, 31)),
    ],
)
def test_phrasings_from_real_calls(text, call, expected):
    assert pe.period_end(text, call) == expected
