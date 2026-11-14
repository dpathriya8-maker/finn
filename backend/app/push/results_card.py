"""Quarterly results card: extract Revenue, EBITDA, PBT, PAT with source page; QoQ and YoY computed in code.

No model is involved. The figures are read from the results PDF by word position (plain text order is
not column order), using the layout SEBI prescribes: the first three numeric columns are the current
quarter, the preceding quarter and the same quarter a year earlier. Every number kept is a token that
is printed in the filing, with its page; a token that cannot be read (a garbled value) is dropped, never
guessed. Changes, margins and EBITDA are computed here, and the card is cross-checked against Yahoo's
quarterly figures where those can be compared fairly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches
from datetime import date
from statistics import mean, median
from typing import Any

EXTRACTOR_VERSION = "2"  # bump whenever the reading changes, so stored readings are redone
ROW_TOLERANCE = 3.0  # points: words closer than this vertically are on the same row
COLUMN_GAP = 10.0  # points: numeric tokens closer than this horizontally belong to one column
COLUMN_MATCH = 18.0  # points: how far a token may sit from its column
TO_CRORE = {"crore": 1.0, "lakh": 0.01, "million": 0.1}
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


@dataclass(frozen=True)
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass(frozen=True)
class Cell:
    text: str  # exactly as printed in the filing
    value: float | None  # what it means, or None if it cannot be read


@dataclass
class Row:
    label: str
    cells: list[Cell | None]  # one per value column, left to right; None where the cell is empty
    page: int


# ----------------------------------------------------------------------------------------- numbers
_NIL = {"", "-", "–", "—", "--", "na", "n.a.", "nil"}


def parse_number(token: str) -> float | None:
    """Figures as Indian filings print them: 332,861 | 1,41,887.37 (lakh grouping) | 6,672.71 | (17,539) |
    17.369.35 (a comma garbled into a dot).

    Anything that is not clearly a number returns None, including dates and garbled text, so it is dropped
    instead of being guessed.
    """
    t = token.strip().replace("−", "-").replace("–", "-").replace("—", "-")
    if t.lower() in _NIL:
        return None
    negative = (t.startswith("(") and t.endswith(")")) or t.startswith("-")
    t = t.strip("()-+ ").replace(" ", "")
    if not t or not re.fullmatch(r"\d[\d.,]*", t):
        return None
    plain = re.fullmatch(r"(\d{1,3}(?:,\d{3})*|\d{1,2}(?:,\d{2})*,\d{3}|\d+)(?:\.(\d+))?", t)
    garbled = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+)[.,](\d{1,2})", t)  # 17.369.35: a comma printed as a dot
    if plain:
        value = float(plain.group(1).replace(",", "") + (f".{plain.group(2)}" if plain.group(2) else ""))
    elif garbled:
        value = float(f"{garbled.group(1).replace('.', '')}.{garbled.group(2)}")
    else:
        return None
    return -value if negative else value


def _is_value(text: str) -> bool:
    """A figure, or a printed dash meaning nil. Anything else on a row is part of its label."""
    return parse_number(text) is not None or text.strip().lower() in _NIL - {""}


# ----------------------------------------------------------------------------------------- layout
def cluster_rows(words: list[Word]) -> list[list[Word]]:
    """Group words into table rows by vertical position, each row left to right."""
    rows: list[list[Word]] = []
    current: list[Word] = []
    for word in sorted(words, key=lambda w: (w.yc, w.x0)):
        if current and abs(word.yc - mean(w.yc for w in current)) > ROW_TOLERANCE:
            rows.append(sorted(current, key=lambda w: w.x0))
            current = []
        current.append(word)
    if current:
        rows.append(sorted(current, key=lambda w: w.x0))
    return rows


def split_row(row: list[Word]) -> tuple[list[Word], list[Word]]:
    """(label words, value words) for one row.

    The values start at the first run of three or more figures in a row; everything before is the label, and a
    stray fragment after the figures (a number the PDF split in two, such as "2,32,") is ignored instead of
    swallowing the figures into the label. A row with fewer figures falls back to: the label runs from the
    first word that is not a figure to the last one, and the figures after it are the values. Figures before
    the label are a serial number and are dropped; figures inside it ("Notes 2 and 3") stay in the label."""
    is_value = [_is_value(w.text) for w in row]
    for start in range(len(row) - 2):
        if all(is_value[start : start + 3]):
            label = row[:start]
            while label and _is_value(label[0].text):  # a serial number before the label
                label = label[1:]
            return label, [w for w, v in zip(row[start:], is_value[start:]) if v]
    if all(is_value):
        return [], list(row)
    first = is_value.index(False)
    last = len(is_value) - 1 - is_value[::-1].index(False)
    return row[first : last + 1], row[last + 1 :]


def _x(word: Word, anchor: str) -> float:
    return word.x1 if anchor == "x1" else (word.x0 + word.x1) / 2


def find_columns(value_rows: list[list[Word]]) -> tuple[list[float], str]:
    """The x position of each numeric column, left to right, and which edge was used. Right-aligned figures
    share a right edge and centred ones a centre; whichever clusters better wins."""
    rows = [[w for w in r if parse_number(w.text) is not None] for r in value_rows]
    rows = [r for r in rows if len(r) >= 3]
    best: tuple[list[float], str, int] = ([], "x1", 0)
    for anchor in ("x1", "xc"):
        xs = sorted(_x(w, anchor) for r in rows for w in r)
        clusters: list[list[float]] = []
        for x in xs:
            if clusters and x - clusters[-1][-1] <= COLUMN_GAP:
                clusters[-1].append(x)
            else:
                clusters.append([x])
        kept = [c for c in clusters if len(c) >= max(3, 0.25 * len(rows))]
        covered = sum(len(c) for c in kept)
        if len(kept) >= 3 and covered > best[2]:
            best = ([mean(c) for c in kept], anchor, covered)
    return best[0], best[1]


@dataclass
class Table:
    rows: list[Row]
    order_read: bool  # the order of the three quarter columns was read from the header dates, not assumed
    current: date | None  # the latest quarter-end among them, when the header was read


def column_order(header: list[Word], columns: list[float], anchor: str) -> tuple[list[int], date] | None:
    """Which of the first three columns is the current quarter, the preceding quarter and the same quarter a
    year earlier, read from the dates in the header. SEBI's order is current, preceding, year-ago and most
    filings follow it, but ITC prints the year-ago quarter second, so the order is read and not assumed.
    Returns the indexes in that order and the current quarter-end, or None if the dates cannot be read."""
    if len(columns) < 3:
        return None
    gap = median([b - a for a, b in zip(columns, columns[1:])]) if len(columns) > 1 else 60.0
    # Each header word belongs to the one nearest column, so neighbouring columns and the page title do not
    # leak into each other. Figures are right-aligned, so a column's header text sits left of its right edge.
    centres = [c - 0.4 * gap if anchor == "x1" else c for c in columns[:3]]
    owned: list[list[Word]] = [[], [], []]
    for word in header:
        middle = (word.x0 + word.x1) / 2
        nearest = min(range(3), key=lambda k: abs(middle - centres[k]))
        if abs(middle - centres[nearest]) <= 0.55 * gap:
            owned[nearest].append(word)
    # the date nearest the figures is the column's own; a title date higher up is not
    dates: list[date | None] = [
        parse_date(" ".join(w.text for w in sorted(ws, key=lambda w: (round(w.yc / 3), w.x0))), last=True) for ws in owned
    ]
    if None in dates or len(set(dates)) != 3:
        return None
    current = max(d for d in dates if d is not None)

    def near(target: date) -> list[int]:
        return [i for i, d in enumerate(dates) if d is not None and abs((d - target).days) <= 12]

    previous, year_ago = near(_shift_months(current, -3)), near(_shift_months(current, -12))
    if len(previous) != 1 or len(year_ago) != 1:
        return None
    return [dates.index(current), previous[0], year_ago[0]], current


def parse_rows(words: list[Word], page: int) -> Table:
    """The table rows of one page: a label and one cell per numeric column, the first three in the order
    current quarter, preceding quarter, same quarter last year."""
    clustered = cluster_rows(words)
    split = [split_row(r) for r in clustered]
    columns, anchor = find_columns([values for _, values in split if values])
    if not columns:
        return Table([], False, None)
    rows: list[Row] = []
    pending = ""
    for label_words, values in split:
        label = " ".join(w.text for w in label_words).strip()
        if not values:
            pending = label  # a wrapped label whose figures sit on the next line
            continue
        cells: list[Cell | None] = [None] * len(columns)
        for word in values:
            nearest = min(range(len(columns)), key=lambda i: abs(columns[i] - _x(word, anchor)))
            if abs(columns[nearest] - _x(word, anchor)) <= COLUMN_MATCH and cells[nearest] is None:
                cells[nearest] = Cell(word.text, parse_number(word.text))
        rows.append(Row(label or pending, cells, page))
        pending = ""
    rows = _drop_serial_columns(rows)
    if len(rows[0].cells if rows else []) < 3:
        return Table(rows, False, None)

    # The body starts at the first row of real figures. A line of years ("2026 2025 2026") is still header: a
    # year parses as a number, so it must not count here or it would cut the years off the column dates.
    def figures(values: list[Word]) -> int:
        return sum(parse_number(w.text) is not None and not re.fullmatch(r"(?:19|20)\d{2}", w.text) for w in values)

    first = next((i for i, (_, values) in enumerate(split) if figures(values) >= 3), 0)
    header = [w for row in clustered[max(0, first - 8) : first] for w in row]
    found = column_order(header, columns[len(columns) - len(rows[0].cells) :], anchor)
    if found is None:
        return Table(rows, False, None)
    order, current = found
    for row in rows:
        row.cells[:3] = [row.cells[i] for i in order]
    return Table(rows, True, current)


def _drop_serial_columns(rows: list[Row]) -> list[Row]:
    """A first column of nothing but 1-2 digit numbers, like the note numbers ITC prints to the right of its
    labels, is not a period. It is dropped while another column holds real figures (decimals or thousands)."""
    while rows and rows[0].cells:
        first = [r.cells[0].text for r in rows if r.cells and r.cells[0] is not None]
        later_real = any(c is not None and re.search(r"[.,]", c.text) for r in rows for c in r.cells[1:])
        if len(first) >= 2 and all(re.fullmatch(r"\d{1,2}", t) for t in first) and later_real:
            rows = [Row(r.label, r.cells[1:], r.page) for r in rows]
        else:
            break
    return rows


def looks_scanned(rows: list[Row]) -> bool:
    """A scanned (OCR'd) filing has figures stuck inside its labels ("(c) Finance costs 712 683 579 l,395 I,"),
    because the reader could not place them in columns. A clean filing has almost none."""
    noisy = 0
    for row in rows:
        digits = [w for w in row.label.split() if re.search(r"\d", w) and not re.fullmatch(r"\(?\w{1,3}\)?|\d{4}", w)]
        noisy += len(digits) >= 3
    return noisy >= 3


# ----------------------------------------------------------------------------------------- reading
def norm_label(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip().lower()
    t = re.sub(r"^[\(\[]?[a-z0-9]{1,4}[\)\].]\s+", "", t)  # "(a) ", "1) ", "iv) "
    t = re.sub(r"\s*\((?:[\d+\-×x/ ,]|and)+\)\s*$", "", t)  # a trailing "(5+6)" or "(1-2)"
    return t.rstrip(" :")


REVENUE_LABELS = [
    r"total revenue from operations", r"revenue from operations", r"total income from operations",
    r"income from operations", r"net sales(?:/income from operations)?", r"sales/income from operations", r"total revenue",
]
_NOT_PBT = re.compile(r"exceptional|associate|joint venture|share of|extraordinary")
_PBT = re.compile(r"^profit(?:\s*/\s*\(?loss\)?|\s*\(?loss\)?)? before tax\b")
_PBT_PRE = re.compile(r"^profit(?:\s*/\s*\(?loss\)?|\s*\(?loss\)?)? before (?:exceptional|extraordinary)")
_PAT = [
    re.compile(r"^profit(?:\s*/\s*\(?loss\)?)? after tax\b"),
    re.compile(r"^net profit(?:\s*/\s*\(?loss\)?)?(?: after tax)?(?: for the (?:period|quarter|year))?"),
    re.compile(r"^profit(?:\s*/\s*\(?loss\)?)? for the (?:period|quarter|year)"),
]
_NOT_PAT = re.compile(r"before|comprehensive|attributable|per share|from discontinued|tax expense")
_OWNERS = re.compile(r"^(?:owners|equity holders|shareholders|equity shareholders)\b|^owners of")
_OCI = re.compile(r"comprehensive|other comprehensive")


def _first_value_row(rows: list[Row], matches) -> Row | None:
    for row in rows:
        if any(cell is not None and cell.value is not None for cell in row.cells[:3]) and matches(norm_label(row.label)):
            return row
    return None


def _quarter(row: Row | None) -> tuple[str | None, ...]:
    """The three figures as printed. A figure that was computed rather than printed has no token (None)."""
    return tuple((row.cells[i].text or None) if row and i < len(row.cells) and row.cells[i] else None for i in range(3))


def _values(row: Row | None) -> tuple[float | None, ...]:
    return tuple(row.cells[i].value if row and i < len(row.cells) and row.cells[i] else None for i in range(3))


def _unit_of(text: str) -> str | None:
    match = re.search(r"\b(crores?|lakhs?|lacs?|millions?|mn)\b", text, re.I)
    if not match:
        return None
    word = match.group(1).lower()
    return "crore" if word.startswith("cr") else "lakh" if word.startswith("la") else "million"


def detect_unit(texts: dict[int, str], pages: list[int]) -> str | None:
    """The unit the figures are printed in: the statement's own page first, then its neighbours (some
    filings state it once, on an earlier page)."""
    for distance in range(4):
        for page in sorted({p + d for p in pages for d in (-distance, distance)}):
            unit = _unit_of(texts.get(page, ""))
            if unit:
                return unit
    return None


def detect_basis(head: str) -> str | None:
    """consolidated or standalone, from the title at the top of the page (whichever is mentioned first)."""
    text = head.lower()
    found = {k: text.find(k) for k in ("consolidated", "standalone", "stand-alone", "stand alone") if k in text}
    if not found:
        return None
    return "consolidated" if min(found, key=found.get) == "consolidated" else "standalone"


def page_head(words: list[Word], rows: int = 12) -> str:
    """The words in the top rows of a page, which is where a statement's title is printed."""
    return " ".join(w.text for row in cluster_rows(words)[:rows] for w in row)


def is_lender(text: str) -> bool:
    return bool(re.search(r"interest income|interest earned|fees and commission", text, re.I))


def _close(label: str, phrase: str, cutoff: float = 0.86) -> bool:
    """OCR-damaged labels ("profit before t!ix") still count as their phrase."""
    return SequenceMatcher(None, label[: len(phrase) + 3], phrase).ratio() >= cutoff


def _is_pbt(label: str) -> bool:
    if _NOT_PBT.search(label):
        return False
    return bool(_PBT.match(label)) or _close(label, "profit before tax")


def _is_pat(label: str) -> bool:
    if _NOT_PAT.search(label):
        return False
    return any(p.match(label) for p in _PAT) or _close(label, "profit after tax") or _close(label, "net profit for the period")


def _looks_like_results(text: str) -> bool:
    """A page worth parsing: "before tax" (or its OCR damage), a revenue word, and a quarter or three months ended."""
    return bool(
        re.search(r"before\s+t\S{1,3}\b", text, re.I)
        and re.search(r"revenue|income from operations|total income|net sales", text, re.I)
        and re.search(r"quarter|three\s+months", text, re.I)
        and re.search(r"ended", text, re.I)
    )


@dataclass
class Extraction:
    basis: str | None
    unit: str | None
    pages: list[int]
    lender: bool
    rows: dict[str, Row | None]  # revenue, total_income, other_income, finance, depreciation, pbt_pre, pbt, pat, pat_owners
    revenue_label: str  # what the filing calls the revenue row we used
    dropped: list[int]  # columns that failed the arithmetic check and are not shown
    scanned: bool  # the text layer is OCR output, so no figure is trusted without independent confirmation
    order_read: bool  # the quarter columns' order came from the header dates
    current: date | None  # the current quarter-end, as read from the header
    warnings: list[str]
    filled: list[int] = field(default_factory=list)  # profit-after-tax columns computed as PBT - tax because the printed figure was unreadable


def _drop_columns(row: Row | None, drop: set[int]) -> Row | None:
    if row is None or not drop:
        return row
    return Row(row.label, [None if i in drop else c for i, c in enumerate(row.cells)], row.page)


def _failed_columns(rev: Row | None, other: Row | None, total: Row | None) -> set[int]:
    """Columns where total income is not revenue plus other income. A misread digit, which is the risk in
    OCR'd filings, shows up here. Needs all three rows, and revenue must not itself be the total-income row."""
    if not (rev and other and total) or rev is total:
        return set()
    bad = set()
    for i in range(3):
        r, o, t = (_values(x)[i] for x in (rev, other, total))
        if None in (r, o, t):
            continue
        if abs((r + o) - t) > 1.5 + 0.003 * abs(t):
            bad.add(i)
    return bad


_STUCK_FIGURES = re.compile(r"(?:\s+[\w.,()\-]*\d[\w.,()\-]*)+$")  # trailing words that contain a digit: "(8-9) 10 4229.33 51B6.55"


def _fill_profit(pat: Row | None, pbt: Row | None, tax: Row | None) -> tuple[Row | None, list[int]]:
    """A profit-for-the-period row with unreadable figures (a digit the PDF's own text layer garbled, or a figure
    stuck in the label, as in ITC's filing) is completed as profit before tax less tax expense, but only when
    that sum reproduces every figure of the row that IS readable. Returns the row and the columns computed."""
    if pat is None or pbt is None or tax is None:
        return pat, []
    p, b, t = _values(pat), _values(pbt), _values(tax)
    present = [i for i in range(3) if p[i] is not None]
    missing = [i for i in range(3) if p[i] is None and b[i] is not None and t[i] is not None]
    if not present or not missing:
        return pat, []
    for i in present:
        if b[i] is None or t[i] is None or abs((b[i] - t[i]) - p[i]) > 0.5 + 0.002 * abs(p[i]):
            return pat, []  # the sum does not describe this row, so it is not used to describe the gaps either
    cells = [*pat.cells, *([None] * (3 - len(pat.cells)))]
    for i in missing:
        cells[i] = Cell("", round(b[i] - t[i], 2))  # no printed token: this figure is computed
    return Row(_STUCK_FIGURES.sub("", pat.label), cells, pat.page), missing


def extract_statement(pages: dict[int, list[Word]], texts: dict[int, str]) -> Extraction | None:
    """Pick the results statement (consolidated when there is one) and read the rows we need."""
    candidates: list[tuple[int, str | None, Table]] = []
    for number in sorted(pages):
        text = texts.get(number, "")
        if not _looks_like_results(text):
            continue
        table = parse_rows(pages[number], number)
        if not any(_is_pbt(norm_label(r.label)) for r in table.rows):
            continue
        basis = detect_basis(page_head(pages[number])) or detect_basis(text[:1500])
        if basis is None and candidates and candidates[-1][0] == number - 1:
            basis = candidates[-1][1]  # a continuation page has no title of its own
        candidates.append((number, basis, table))
    if not candidates:
        return None

    rank = {"consolidated": 0, None: 1, "standalone": 2}
    start = min(range(len(candidates)), key=lambda i: (rank[candidates[i][1]], i))
    chosen = [candidates[start]]
    for later in candidates[start + 1 :]:
        if later[0] == chosen[-1][0] + 1 and later[1] == chosen[0][1]:
            chosen.append(later)
    basis = chosen[0][1]
    rows = [r for c in chosen for r in c[2].rows]
    order_read = all(c[2].order_read for c in chosen)
    current = next((c[2].current for c in chosen if c[2].current), None)
    page_numbers = [c[0] for c in chosen]
    text = " ".join(texts.get(n, "") for n in page_numbers)
    warnings: list[str] = []
    if not order_read:
        warnings.append("The order of the quarter columns could not be read from the header, so the usual order is assumed.")

    revenue, revenue_label = None, ""
    for pattern in REVENUE_LABELS:
        revenue = _first_value_row(rows, lambda label, p=pattern: re.match(p + r"\b", label) is not None)
        if revenue:
            break
    if revenue is None:
        revenue = _first_value_row(rows, lambda label: _close(label, "revenue from operations"))
    total_income = _first_value_row(rows, lambda label: label.startswith("total income") or _close(label, "total income"))
    if revenue is None and total_income is not None:
        revenue = total_income
        warnings.append("The filing's revenue row was not found, so total income is shown as revenue.")
    revenue_label = norm_label(revenue.label) if revenue else ""

    other_income = _first_value_row(rows, lambda label: label.startswith("other income") or _close(label, "other income"))
    drop = _failed_columns(revenue, other_income, total_income)
    if 0 in drop:
        return None  # the current quarter fails its own arithmetic: better no card than a wrong one
    if drop:
        warnings.append("An earlier-period column failed the check total income = revenue + other income and is not shown.")

    pat = _first_value_row(rows, _is_pat)
    owners = None
    if pat is not None:
        position = rows.index(pat)
        for row in rows[position + 1 : position + 16]:
            label = norm_label(row.label)
            if _OCI.search(label):
                break
            if _OWNERS.match(label) and any(c and c.value is not None for c in row.cells[:3]):
                owners = row
                break

    pbt_row = _first_value_row(rows, _is_pbt)
    tax = _first_value_row(rows, lambda label: bool(re.match(r"(?:total )?tax expenses?\b", label)))
    pat, filled = _fill_profit(pat, pbt_row, tax)

    found = {
        "revenue": revenue,
        "total_income": total_income,
        "other_income": other_income,
        "finance": _first_value_row(rows, lambda label: bool(re.match(r"finance costs?|interest and finance|interest expense", label))),
        "depreciation": _first_value_row(rows, lambda label: label.startswith("depreciation")),
        "excise": _first_value_row(rows, lambda label: label.startswith("excise duty")),
        "pbt_pre": _first_value_row(rows, lambda label: bool(_PBT_PRE.match(label))),
        "pbt": pbt_row,
        "pat": pat,
        "pat_owners": owners,
    }
    return Extraction(
        basis=basis,
        unit=detect_unit(texts, page_numbers),
        pages=page_numbers,
        lender=is_lender(text),
        rows={k: _drop_columns(v, drop) for k, v in found.items()},
        revenue_label=revenue_label,
        dropped=sorted(drop),
        scanned=looks_scanned(rows),
        order_read=order_read,
        current=current,
        warnings=warnings,
        filled=[i for i in filled if i not in drop],
    )


# ----------------------------------------------------------------------------------------- the card
def _month(name: str) -> int | None:
    key = name.lower()
    if key in MONTHS:
        return MONTHS[key]
    close = get_close_matches(key, list(MONTHS), n=1, cutoff=0.6)  # a typo as printed in Reliance's header: "Seo'25"
    return MONTHS[close[0]] if close else None


def parse_date(text: str, *, last: bool = False) -> date | None:
    """A date in text, in any of the ways filings write it: the first one, or the last with last=True."""
    patterns = [
        (r"(\d{1,2})(?:st|nd|rd|th)?[\s.\-/']*([A-Za-z]{3,9})[\s.,\-/']*(\d{2,4})", "dmy_name"),
        (r"([A-Za-z]{3,9})[\s.,\-/']*(\d{1,2})(?:st|nd|rd|th)?[\s.,\-/']*(\d{4})", "mdy_name"),
        (r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", "dmy_num"),
    ]
    found: list[tuple[int, date]] = []
    for pattern, kind in patterns:
        for m in re.finditer(pattern, text):
            try:
                if kind == "dmy_num":
                    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif kind == "dmy_name":
                    day, month, year = int(m.group(1)), _month(m.group(2)), int(m.group(3))
                else:
                    month, day, year = _month(m.group(1)), int(m.group(2)), int(m.group(3))
                if month is None:
                    continue
                year += 2000 if year < 100 else 0
                found.append((m.start(), date(year, month, day)))
            except ValueError:
                continue
    if not found:
        return None
    return (max if last else min)(found, key=lambda item: item[0])[1]


def period_end_from_text(text: str) -> date | None:
    """The quarter-end the filing is about, from its own words ("... quarter and half year ended 30 September 2026")."""
    match = re.search(r"(?:quarter|half[- ]year|six months|nine months|year|period)[^.]{0,40}?ended(?: on)?\s+(.{0,40})", text, re.I)
    return parse_date(match.group(1)) if match else parse_date(text)


def _shift_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    last = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(day.day, last))


def fiscal_label(end: date) -> str:
    """Indian fiscal year: April to March. September 2026 is Q2 FY27."""
    quarter = ((end.month - 4) % 12) // 3 + 1
    year = end.year + (1 if end.month >= 4 else 0)
    return f"Q{quarter} FY{year % 100:02d}"


def pct_change(current: float | None, previous: float | None) -> float | None:
    """Percent change, or None when it would mean nothing (no base, or a negative base)."""
    if current is None or previous is None or previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _swing(current: float | None, previous: float | None) -> str | None:
    if current is None or previous is None:
        return None
    if previous <= 0 < current:
        return "turned profit"
    if previous > 0 >= current:
        return "turned loss"
    return None


def _metric(key: str, label: str, row: Row | None, scale: float, *, derived: str = "") -> dict[str, Any] | None:
    values = _values(row)
    if row is None or all(v is None for v in values):
        return None
    cr = [None if v is None else round(v * scale, 2) for v in values]
    metric = {
        "key": key,
        "label": label,
        "current": cr[0],
        "previous": cr[1],
        "year_ago": cr[2],
        "qoq_pct": pct_change(cr[0], cr[1]),
        "yoy_pct": pct_change(cr[0], cr[2]),
        "qoq_swing": _swing(cr[0], cr[1]),
        "yoy_swing": _swing(cr[0], cr[2]),
        "printed": {"label": row.label, "page": row.page, "tokens": list(_quarter(row))},
    }
    if derived:
        metric["derived"] = derived
    return metric


def _ebitda(rows: dict[str, Row | None], lender: bool, scale: float) -> dict[str, Any] | None:
    """Not reported by companies: profit before exceptional items and tax, plus finance costs and
    depreciation, less other income. Every part must be present for all three periods or it is omitted."""
    if lender:
        return None
    parts = [rows.get("pbt_pre") or rows.get("pbt"), rows.get("finance"), rows.get("depreciation"), rows.get("other_income")]
    if any(p is None for p in parts):
        return None
    pbt, fin, dep, oth = (_values(p) for p in parts)
    out: list[float | None] = []
    for i in range(3):
        if None in (pbt[i], fin[i], dep[i], oth[i]):
            out.append(None)
        else:
            out.append(round((pbt[i] + fin[i] + dep[i] - oth[i]) * scale, 2))
    if out[0] is None:
        return None
    return {
        "key": "ebitda", "label": "EBITDA", "current": out[0], "previous": out[1], "year_ago": out[2],
        "qoq_pct": pct_change(out[0], out[1]), "yoy_pct": pct_change(out[0], out[2]), "qoq_swing": None, "yoy_swing": None,
        "derived": "Computed here, not reported: profit before exceptional items and tax + finance costs + depreciation − other income",
        "printed": {"label": "computed", "page": parts[0].page, "tokens": []},
    }


def _margin(metric: dict[str, Any] | None, revenue: dict[str, Any] | None, field: str) -> float | None:
    if not metric or not revenue or metric.get(field) is None or not revenue.get(field):
        return None
    return round(metric[field] / revenue[field] * 100, 1)


def cross_check(card: dict[str, Any], yahoo: list[dict[str, Any]], ex: Extraction, period_end: date | None) -> dict[str, Any]:
    """Compare the current quarter with Yahoo's figure for the same quarter, where that is a fair comparison.
    Yahoo's revenue is not comparable for lenders and its profit is the owners' share, so those cases are skipped."""
    base = {"against": "Yahoo Finance quarterly figures"}
    if period_end is None:
        return {**base, "status": "unavailable", "note": "The quarter-end date could not be read."}
    match = next((q for q in yahoo if abs((date.fromisoformat(q["period_end"]) - period_end).days) <= 5), None)
    if match is None:
        return {**base, "status": "unavailable", "note": "Yahoo has not published this quarter yet."}

    metrics = {m["key"]: m for m in card["metrics"]}
    pairs = []
    if not ex.lender and metrics.get("revenue"):
        excise = (_values(ex.rows.get("excise"))[0] or 0.0) * TO_CRORE.get(ex.unit or "", 0.0) if ex.rows.get("excise") else 0.0
        pairs.append(("revenue", metrics["revenue"]["current"], match.get("revenue_cr"), 2.5, excise))
    if metrics.get("pbt"):
        pairs.append(("pbt", metrics["pbt"]["current"], match.get("pbt_cr"), 1.5, 0.0))
    own = metrics.get("pat_owners") or (metrics.get("pat") if ex.basis == "standalone" else None)
    if own:
        pairs.append(("pat", own["current"], match.get("net_income_cr"), 2.5, 0.0))

    details = []
    for key, filing, theirs, tolerance, excise in pairs:
        if filing is None or theirs in (None, 0):
            continue
        # Yahoo's revenue excludes excise duty (ITC's differs from the filing by exactly that), so either counts.
        diff = round(min(abs(filing - theirs), abs(filing - excise - theirs)) / abs(theirs) * 100, 1)
        details.append({"metric": key, "filing": filing, "yahoo": theirs, "diff_pct": diff, "ok": diff <= tolerance})
    if not details:
        return {**base, "status": "unavailable", "note": "Yahoo has nothing comparable for this quarter."}
    if all(d["ok"] for d in details):
        return {**base, "status": "ok", "details": details, "note": "Matches Yahoo Finance for the same quarter."}
    return {
        **base,
        "status": "differs",
        "details": details,
        "note": "Differs from Yahoo Finance. Restated figures, a different definition or a data lag can explain this; the filing is the source of truth.",
    }


def tone_for(metrics: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """bad, watch, good or neutral, with a plain reason. There is no consensus estimate here, so this judges
    only the direction against last year, never "beat" or "miss"."""
    pat, rev = metrics.get("pat") or metrics.get("pbt"), metrics.get("revenue")
    if pat is None:
        return "neutral", ""
    yoy = pat["yoy_pct"]
    rev_yoy = rev["yoy_pct"] if rev else None
    swing = pat["yoy_swing"]
    what = "Profit" if metrics.get("pat") else "Pre-tax profit"
    tail = f"; revenue {'up' if rev_yoy >= 0 else 'down'} {abs(rev_yoy):.0f}%" if rev_yoy is not None else ""
    if swing == "turned loss":
        return "bad", f"{what} turned into a loss from a year ago{tail}"
    if swing == "turned profit":
        return "good", f"{what} turned positive from a loss a year ago{tail}"
    if yoy is None:
        return "neutral", ""
    word = f"{what} {'up' if yoy >= 0 else 'down'} {abs(yoy):.0f}% from a year ago{tail}"
    if yoy <= -20 or (yoy < 0 and rev_yoy is not None and rev_yoy < 0):
        return "bad", word
    if yoy < -5 or (rev_yoy is not None and rev_yoy < 0):
        return "watch", word
    if yoy >= 15 and (rev_yoy is None or rev_yoy > 0):
        return "good", word
    return "neutral", word


def verified_columns(ex: Extraction, yahoo: list[dict[str, Any]], period_end: date | None) -> set[int]:
    """For a scanned filing: the columns (0 current, 1 previous quarter, 2 year ago) whose profit before tax
    Yahoo confirms to within 1.5%. A misread digit in OCR text still parses as a number, so for these filings a
    figure is shown only where an independent source agrees with it."""
    row, scale = ex.rows.get("pbt"), TO_CRORE.get(ex.unit or "", 0.0)
    if row is None or period_end is None or not scale:
        return set()
    confirmed: set[int] = set()
    for column, months in enumerate((0, -3, -12)):
        value = _values(row)[column]
        target = _shift_months(period_end, months)
        match = next((q for q in yahoo if abs((date.fromisoformat(q["period_end"]) - target).days) <= 5), None)
        theirs = match.get("pbt_cr") if match else None
        if value is not None and theirs and abs(value * scale - theirs) / abs(theirs) <= 0.015:
            confirmed.add(column)
    return confirmed


_COLUMN_NAMES = ("this quarter", "the preceding quarter", "the year-ago quarter")


def _filled_note(row: Row | None, filled: list[int]) -> str:
    """Says which profit figures are computed, how, and which printed figure shows that the sum is right."""
    if row is None:
        return ""
    has = lambda i: i < len(row.cells) and row.cells[i] is not None
    shown = [i for i in filled if has(i)]
    printed = [i for i in range(3) if has(i) and row.cells[i].text]
    if not shown:
        return ""
    note = f"The filing's printed figure for {' and '.join(_COLUMN_NAMES[i] for i in shown)} could not be read, so it is computed as profit before tax less tax expense."
    if printed:
        note += f" The same sum reproduces the printed figure for {' and '.join(_COLUMN_NAMES[i] for i in printed)}."
    return note


def build_card(ex: Extraction, *, period_end: date | None, yahoo: list[dict[str, Any]], source_url: str | None) -> dict[str, Any]:
    scale = TO_CRORE.get(ex.unit or "", 0.0)
    if scale == 0.0:
        return _failed("The unit of the figures (crore, lakh or million) could not be read.")

    rows, verification = ex.rows, None
    if ex.scanned:
        confirmed = verified_columns(ex, yahoo, period_end)
        if 0 not in confirmed:
            return _failed("This filing is a scan and its figures could not be confirmed against an independent source, so none are shown. Open the filing to read them.")
        rows = {k: _drop_columns(v, {0, 1, 2} - confirmed) for k, v in ex.rows.items()}
        verification = "Scanned filing: each period is shown only where Yahoo Finance's profit before tax agrees with it."

    ordered = [
        _metric("revenue", "Revenue", rows["revenue"], scale),
        _ebitda(rows, ex.lender, scale),
        _metric("pbt", "Profit before tax", rows["pbt"], scale),
        _metric("pat", "Profit after tax", rows["pat"], scale, derived=_filled_note(rows["pat"], ex.filled)),
        _metric("pat_owners", "Profit to owners", rows["pat_owners"], scale),
    ]
    metrics = [m for m in ordered if m and m["current"] is not None]  # a metric with no readable current figure is not shown
    by_key = {m["key"]: m for m in metrics}
    if "pbt" not in by_key and "pat" not in by_key:
        return _failed("The profit rows could not be read reliably from the filing.")
    warnings = list(ex.warnings)
    status = "ok"
    if "revenue" not in by_key:
        status = "partial"
        warnings.append("Revenue could not be read reliably from this filing, so only profit is shown.")

    # "Profit to owners" is only shown when it differs from total profit, so a company without minorities shows one profit row.
    if "pat_owners" in by_key and "pat" in by_key and by_key["pat_owners"]["current"] == by_key["pat"]["current"]:
        metrics = [m for m in metrics if m["key"] != "pat_owners"]

    revenue = by_key.get("revenue")
    margins = {
        k: {"current": _margin(by_key.get(k), revenue, "current"), "year_ago": _margin(by_key.get(k), revenue, "year_ago")}
        for k in ("ebitda", "pbt", "pat")
        if by_key.get(k)
    }
    card: dict[str, Any] = {
        "type": "results",
        "status": status,
        "verification": verification,
        "basis": ex.basis or "not stated",
        "unit_printed": ex.unit,
        "unit_shown": "Rs crore",
        "period": {
            "label": fiscal_label(period_end) if period_end else "Latest quarter",
            "current": period_end.isoformat() if period_end else None,
            "previous": _shift_months(period_end, -3).isoformat() if period_end else None,
            "year_ago": _shift_months(period_end, -12).isoformat() if period_end else None,
        },
        "source": {"url": source_url, "pages": ex.pages},
        "metrics": metrics,
        "margins": margins,
        "warnings": warnings,
        "extractor": EXTRACTOR_VERSION,
    }
    card["check"] = cross_check(card, yahoo, ex, period_end)
    card["tone"], card["tone_reason"] = tone_for(by_key)
    return card


# ----------------------------------------------------------------------------------------- from a PDF
def extract_from_pdf(pdf: bytes) -> tuple[Extraction | None, date | None]:
    """Read the results statement out of a PDF. Returns the extraction and, as a fallback for the quarter-end,
    the date that the PDF's first page names."""
    import pymupdf  # imported here so the API starts fast; only the pipeline reads PDFs

    document = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        texts = {i + 1: document[i].get_text("text") for i in range(document.page_count)}
        wanted = [n for n, t in texts.items() if re.search(r"before\s+t\S{1,3}\b", t, re.I) and re.search(r"quarter|three\s+months", t, re.I)]
        pages: dict[int, list[Word]] = {}
        for n in wanted:
            page = document[n - 1]
            # A rotated page (Tata Steel's statements are turned 270 degrees) reports its words in unrotated
            # coordinates, where one table row is one column. Map them to how the page is actually read.
            turn = page.rotation_matrix
            boxes = [(pymupdf.Rect(x0, y0, x1, y1) * turn, w) for x0, y0, x1, y1, w, *_ in page.get_text("words")]
            pages[n] = [Word(r.x0, r.y0, r.x1, r.y1, w) for r, w in boxes]
        return extract_statement(pages, texts), period_end_from_text(texts.get(1, ""))
    finally:
        document.close()


# ----------------------------------------------------------------------------------------- reading vs. the card
# Reading the PDF is slow and gives the same answer every time, so it is done once and kept (as plain JSON).
# The card is built from that reading on every run, because its cross-check depends on Yahoo's data, which
# changes when Yahoo publishes the quarter.
def _row_dict(row: Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"label": row.label, "page": row.page, "cells": [None if c is None else [c.text, c.value] for c in row.cells]}


def _row_from(data: dict[str, Any] | None) -> Row | None:
    if data is None:
        return None
    return Row(data["label"], [None if c is None else Cell(c[0], c[1]) for c in data["cells"]], data["page"])


def extraction_to_dict(ex: Extraction) -> dict[str, Any]:
    return {
        "basis": ex.basis, "unit": ex.unit, "pages": ex.pages, "lender": ex.lender,
        "rows": {key: _row_dict(row) for key, row in ex.rows.items()},
        "revenue_label": ex.revenue_label, "dropped": ex.dropped, "scanned": ex.scanned, "order_read": ex.order_read,
        "current": ex.current.isoformat() if ex.current else None, "warnings": ex.warnings, "filled": ex.filled,
    }


def extraction_from_dict(data: dict[str, Any]) -> Extraction:
    return Extraction(
        basis=data["basis"], unit=data["unit"], pages=list(data["pages"]), lender=data["lender"],
        rows={key: _row_from(row) for key, row in data["rows"].items()},
        revenue_label=data["revenue_label"], dropped=list(data["dropped"]), scanned=data["scanned"],
        order_read=data["order_read"], current=date.fromisoformat(data["current"]) if data["current"] else None,
        warnings=list(data["warnings"]), filled=list(data.get("filled", [])),
    )


def _failed(reason: str) -> dict[str, Any]:
    return {"type": "results", "status": "failed", "reason": reason, "extractor": EXTRACTOR_VERSION}


def read_pdf(pdf: bytes) -> dict[str, Any]:
    """Read a results PDF into plain data that can be stored. Never raises for a bad PDF: the outcome says why
    nothing was read, and that outcome is as repeatable as a success, so it is stored too."""
    try:
        extraction, first_page_period = extract_from_pdf(pdf)
    except Exception as exc:  # a corrupt or encrypted PDF must not stop the pipeline
        return {"error": f"The PDF could not be read ({type(exc).__name__})."}
    if extraction is None:
        return {"error": "No quarterly results statement was found in the PDF."}
    return {"extraction": extraction_to_dict(extraction), "first_page_period": first_page_period.isoformat() if first_page_period else None}


def card_from_reading(reading: dict[str, Any], *, hint_text: str, yahoo: list[dict[str, Any]], source_url: str | None) -> dict[str, Any]:
    try:
        if "error" in reading:
            return _failed(reading["error"])
        extraction = extraction_from_dict(reading["extraction"])
        first = reading.get("first_page_period")
        period_end = extraction.current or period_end_from_text(hint_text) or (date.fromisoformat(first) if first else None)
        return build_card(extraction, period_end=period_end, yahoo=yahoo, source_url=source_url)
    except (KeyError, TypeError, ValueError):  # a stored reading from an older layout: treat it as unreadable
        return _failed("The stored reading of this filing could not be used.")


def results_card_from_pdf(pdf: bytes, *, hint_text: str, yahoo: list[dict[str, Any]], source_url: str | None) -> dict[str, Any]:
    """The whole path: PDF bytes to a finished card."""
    return card_from_reading(read_pdf(pdf), hint_text=hint_text, yahoo=yahoo, source_url=source_url)
