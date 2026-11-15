"""When is a promise due? Turn the time frame management gave ("Q3 FY27", "second half", "by March", "next year") into the
last day of that period, on the Indian fiscal calendar (FY27 = April 2026 to March 2027).

This is code, not a model, on purpose: whether a promise is still open or its time has passed decides the verdict, so a
model's guess about dates must not. The extraction prompt asks the model for a canonical period ("Q3 FY27", "H2 FY27",
"FY27", "Mar 2027", "CY2027"); anything it writes loosely is read here too, relative to the day of the call.
Returns None when no period can be read: such a promise has no deadline and is not tracked.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

_MONTHS = {name: n for n, name in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "eighteen": 18, "twenty-four": 24}
_NONE_WORDS = {"", "none", "null", "n/a", "na", "not stated", "unspecified", "ongoing", "going forward", "medium term", "long term"}


def _fy_full(raw: str, second: str | None = None) -> int:
    """'27' or '2027' -> 2027; for a range such as 'FY2026-27' the later year wins."""
    text = second or raw
    year = int(text)
    if year < 100:
        year += 2000
    if second and len(second) == 2 and len(raw) == 4:  # "2026-27": the second part is the short form of the later year
        year = int(raw[:2] + second)
    return year


def fiscal_year_of(day: date) -> int:
    """The fiscal year a day falls in, as the year it ends: 5 Aug 2026 -> 2027."""
    return day.year + 1 if day.month >= 4 else day.year


def quarter_end(q: int, fy: int) -> date:
    month = {1: 6, 2: 9, 3: 12, 4: 3}[q]
    year = fy if q == 4 else fy - 1
    return date(year, month, calendar.monthrange(year, month)[1])


def half_end(h: int, fy: int) -> date:
    return date(fy - 1, 9, 30) if h == 1 else date(fy, 3, 31)


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    return month_end(year, month + 1)


def _first_end_on_or_after(ends, ref: date) -> date:
    return min(e for e in ends if e >= ref)


def _quarter_ends_around(ref: date, q: int) -> list[date]:
    base = fiscal_year_of(ref)
    return [quarter_end(q, fy) for fy in (base - 1, base, base + 1)]


def _half_ends_around(ref: date, h: int) -> list[date]:
    base = fiscal_year_of(ref)
    return [half_end(h, fy) for fy in (base - 1, base, base + 1)]


# The patterns, tried in this order. Each match is blanked out of the text so that "Q1 FY27" is not also read as "FY27".
_FY = r"(?:fy|f\.y\.?)\s*['’]?\s*(\d{4}|\d{2})(?:\s*[-–/]\s*(\d{2,4}))?"
_QUARTER_FY = re.compile(rf"\b(?:q\s*([1-4])|([1-4])\s*q)\s*[-,]?\s*(?:of\s+)?{_FY}")
_HALF_FY = re.compile(rf"\b(?:h\s*([12])|(first|second)\s+half)\s*(?:of\s+)?[-,]?\s*{_FY}")
_FY_ONLY = re.compile(rf"\b{_FY}")
_FISCAL_WORD_YEAR = re.compile(r"\b(?:financial|fiscal)\s+year\s*(\d{4})(?:\s*[-–/]\s*(\d{2,4}))?")
_CALENDAR = re.compile(r"\b(?:cy\s*['’]?\s*|calendar\s+(?:year\s+)?)(\d{4})\b")
_MON = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)"
_MONTH_YEAR = re.compile(rf"\b({_MON})\b\.?,?\s*(?:['’]\s*(\d{{2}})|(\d{{4}}))\b")
# "by March", "in October, November", "before end of December": a month with no year, only after a word that makes it a date
# ("may" and "march" are also ordinary words, and "market" must never be read as March).
_MONTH_PREP = re.compile(rf"\b(?:by|in|for|between|end\s+of|before|until|till|through|during)\s+(?:the\s+)?(?:month\s+of\s+)?(?:end\s+of\s+)?((?:{_MON}\b\.?(?:\s*(?:,|and|or|/|-|to)\s*)?)+)")
_MONTH_WORD = re.compile(rf"\b({_MON})\b")
_BARE_QUARTER = re.compile(r"\b(?:q\s*([1-4])|([1-4])\s*q)\b")
_BARE_HALF = re.compile(r"\b(?:h\s*([12])|(first|second)\s+half)\b")
_THIS_YEAR = re.compile(r"\b(?:this\s+(?:fiscal\s+|financial\s+)?year|current\s+(?:fiscal\s+|financial\s+)?year|full[- ]year|year[- ]end|end\s+of\s+the\s+year|exit(?:ing)?\s+the\s+year|rest\s+of\s+the\s+year|remainder\s+of\s+the\s+year|for\s+the\s+year)\b")
_NEXT_YEAR = re.compile(r"\b(?:next\s+(?:fiscal\s+|financial\s+)?year|next\s+fy|following\s+year)\b")
_COMING_YEAR = re.compile(r"\b(?:in|over|during|for)\s+the\s+coming\s+year\b")  # the next twelve months, not the next fiscal year
_NEXT_QUARTER = re.compile(r"\b(?:next|coming|following)\s+quarter\b")
_COUNT = r"(\d+(?:\.\d+)?|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r"|an?)"
# "in the next 2 years", "within a year's time", "in the 6 months' time", "over a period of next 15-odd months", "next 3 to 4 years"
_WITHIN = re.compile(rf"\b(?:next|coming|within|over(?:\s+a\s+period\s+of)?(?:\s+the\s+next)?|in(?:\s+the)?(?:\s+next)?)\s+(?:next\s+)?{_COUNT}(?:-odd)?(?:\s*(?:to|-|–|or)\s*(\d+))?\s+(year|month|quarter)s?'?")
# "first half of this year", "Q3 of next year", "second quarter of the year": a part of the fiscal year the call is in (or the next one)
_PART_OF_YEAR = re.compile(r"\b(?:q\s*([1-4])|([1-4])\s*q|h\s*([12])|(first|second)\s+half|(first|second|third|fourth)\s+quarter)\s+(?:of|in)\s+(this|the\s+current|the|next)\s+(?:fiscal\s+|financial\s+)?(?:year|fy)\b")
_ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_BARE_YEAR = re.compile(r"\b(20[2-4]\d)\b(?!\s*(?:crore|cr\b|lakh|mw|gw|%|bn|million|billion|bps))")


def _month_from(word: str) -> int | None:
    return _MONTHS.get(word.strip(" .,").lower()[:3])


def period_end(text: str | None, call_date: date | None) -> date | None:
    """The last day of the period `text` names, or None if it names none. `call_date` anchors anything relative
    ("this year", "by March", "second half"): the first such period that has not ended by the day of the call."""
    if text is None or text.strip().lower() in _NONE_WORDS:
        return None
    s = " ".join(text.lower().replace("’", "'").split())
    ends: list[date] = []
    ref = call_date

    def take(pattern: re.Pattern[str], handler) -> None:
        nonlocal s
        for m in list(pattern.finditer(s)):
            end = handler(m)
            if end is not None:
                ends.append(end)
        s = pattern.sub(" ", s)

    take(_QUARTER_FY, lambda m: quarter_end(int(m.group(1) or m.group(2)), _fy_full(m.group(3), m.group(4))))
    take(_HALF_FY, lambda m: half_end(int(m.group(1)) if m.group(1) else (1 if m.group(2) == "first" else 2), _fy_full(m.group(3), m.group(4))))
    take(_FY_ONLY, lambda m: date(_fy_full(m.group(1), m.group(2)), 3, 31))
    take(_FISCAL_WORD_YEAR, lambda m: date(_fy_full(m.group(1), m.group(2)), 3, 31))
    take(_CALENDAR, lambda m: date(int(m.group(1)), 12, 31))

    def month_year(m: re.Match[str]) -> date | None:
        month = _month_from(m.group(1))
        year = int(m.group(3)) if m.group(3) else 2000 + int(m.group(2))
        return month_end(year, month) if month else None

    take(_MONTH_YEAR, month_year)

    if ref is not None:
        # Relative terms need the day of the call. Months without a year: the first month-end on or after the call.
        def months_after(m: re.Match[str]) -> date | None:
            found = [mm for w in _MONTH_WORD.finditer(m.group(1)) if (mm := _month_from(w.group(0)))]
            candidates = [_first_end_on_or_after([month_end(y, mm) for y in (ref.year, ref.year + 1)], ref) for mm in found]
            return max(candidates) if candidates else None

        def part_of_year(m: re.Match[str]) -> date | None:
            fy = fiscal_year_of(ref) + (1 if m.group(6) == "next" else 0)
            if m.group(3) or m.group(4):
                return half_end(int(m.group(3)) if m.group(3) else _ORDINAL[m.group(4)], fy)
            return quarter_end(int(m.group(1) or m.group(2) or _ORDINAL[m.group(5)]), fy)

        take(_PART_OF_YEAR, part_of_year)
        take(_MONTH_PREP, months_after)
        take(_BARE_QUARTER, lambda m: _first_end_on_or_after(_quarter_ends_around(ref, int(m.group(1) or m.group(2))), ref))
        take(_BARE_HALF, lambda m: _first_end_on_or_after(_half_ends_around(ref, int(m.group(1)) if m.group(1) else (1 if m.group(2) == "first" else 2)), ref))
        take(_NEXT_QUARTER, lambda m: _first_end_on_or_after([quarter_end(q, fiscal_year_of(ref) + k) for q in (1, 2, 3, 4) for k in (0, 1)], ref))
        take(_THIS_YEAR, lambda m: date(fiscal_year_of(ref), 3, 31))
        take(_NEXT_YEAR, lambda m: date(fiscal_year_of(ref) + 1, 3, 31))
        take(_COMING_YEAR, lambda m: _add_months(ref, 12))

        def within(m: re.Match[str]) -> date | None:
            raw = m.group(1)
            n = float(_NUMBER_WORDS.get(raw) or (1 if raw in ("a", "an") else raw))
            if m.group(2):  # "3 to 4 years": the later of the two
                n = max(n, float(m.group(2)))
            return _add_months(ref, round(n * {"year": 12, "month": 1, "quarter": 3}[m.group(3)]))

        take(_WITHIN, within)
    take(_BARE_YEAR, lambda m: date(int(m.group(1)), 12, 31))
    return max(ends) if ends else None


def label(day: date) -> str:
    """'31 Mar 2027'."""
    return f"{day.day} {calendar.month_abbr[day.month]} {day.year}"
