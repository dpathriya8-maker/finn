"""Management-change card: who, in what role, what happened, from when, and what the filing itself says about them.

No model is involved. Every fact shown is a literal piece of the filing (with its page), found by rules: the person
and role from the announcement's own one-line headline or from the sentence that states the event, the date from
the words "effective ..." next to it, and the bio from the filing's own "Profile" section, which SEBI's disclosure
format (Schedule III) asks companies to include for an appointment. A rule that finds nothing shows nothing; it
never fills a gap with a guess. A short web bio of an incoming person is a separate, optional step that needs search
and model keys (see docs/decisions.md); it is not part of this module.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.push.results_card import parse_date

EXTRACTOR_VERSION = "m1"
PROFILE_MAX_CHARS = 560
PROFILE_MAX_SENTENCES = 3
EVENT_WINDOW = 700  # characters after an event sentence in which its date and term are looked for

_TITLE = r"(?:Mr|Mrs|Ms|Miss|Dr|Shri|Smt|Prof|Capt|Col|MR|MRS|MS|DR|SHRI|SMT|PROF)\.?"
_ROLE_WORD = r"(?:Chief|Managing|Whole|Director|President|Chairman|Chairperson|Company|Independent|Non|Executive|Senior|Vice|Head|Officer|Additional|Nominee)"
_NAME_TOKEN = rf"(?!{_ROLE_WORD}\b)[A-Z][A-Za-z'’\-]*\.?"
# The patterns below are case-insensitive for their keywords, but a name is capitalised words and nothing else: without
# turning the flag off here, "has" in "Mr. A. Kumar has resigned" would be read as part of the name.
NAME = rf"(?-i:{_TITLE}\s+(?:{_NAME_TOKEN}\s+){{0,4}}{_NAME_TOKEN})"
_DIN = r"(?:\s*\(\s*DIN\s*[:\-]?\s*(?P<din>\d{7,8})\s*\))?"

KINDS: list[tuple[str, str, str]] = [  # (kind, direction, pattern): the first that matches wins
    ("re-appointment", "in", r"re-?\s?appoint\w*"),
    ("redesignation", "in", r"re-?designat\w*|change in designation|elevat\w+|promot\w+"),
    ("appointment", "in", r"appoint\w*|induct\w*|nominat\w+|join(?:s|ed)\b"),
    ("resignation", "out", r"resign\w*"),
    ("retirement", "out", r"retire\w*|superannuat\w*"),
    ("death", "out", r"demise|passed away|death"),
    ("removal", "out", r"removal|removed|terminat\w+"),
    ("cessation", "out", r"cessation|cease[sd]?\b|completion of (?:his|her|their) (?:term|tenure)|steps? down|relinquish\w*"),
]

_AS = r"(?:as|from|to)\s+(?:the\s+|an?\s+)?"
# A role may itself contain commas ("Non-Executive, Non-Independent Director"), so it ends only at the end of the text,
# a full stop, or the words that start the date, term or reason that follow it.
_ROLE_END = (
    r"(?=$|(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bMrs)(?<!\bProf)(?<!\bShri)(?<!\bSmt)\.(?:\s|$)|;|"  # not the full stop of "Ms."
    r",?\s+(?:w\.?e\.?f\.?|effective|with effect|for a (?:period|term)|consequent|pursuant|"
    r"subject to|in terms of|from the (?:close|closure)|upon|due to|on account of)\b"
    r"|\s+and\s+(?:the\s+)?(?:re-?\s?appointment|appointment|resignation|retirement|cessation)\b)"  # a second person in the same sentence
)
_NOUN = re.compile(
    rf"(?P<kind>re-?\s?appointment|appointment|resignation|retirement|cessation|demise|removal|re-?designation)\s+of\s+(?P<name>{NAME}){_DIN}\s*,?\s*{_AS}(?P<role>.{{3,110}}?){_ROLE_END}",
    re.I,
)
_CEASE = re.compile(
    rf"(?P<name>{NAME}){_DIN}\s*,?[^.]{{0,160}}?\b(?:will\s+)?(?P<kind>cease[sd]?)\s+to\s+(?:hold|be)\s+(?:the\s+)?(?:position|office|designation)?(?:\s+of)?\s+(?P<role>.{{3,110}}?){_ROLE_END}",
    re.I,
)
_VERB_OUT = re.compile(
    rf"(?P<name>{NAME}){_DIN}\s*,?\s+(?:has\s+|have\s+)?(?P<kind>resigned|tendered\s+(?:his|her)\s+resignation|(?:will\s+)?retire[sd]?)\b[^.]{{0,40}}?\s{_AS}(?:position of\s+)?(?P<role>.{{3,110}}?){_ROLE_END}",
    re.I,
)
_VERB_IN = re.compile(
    rf"(?P<kind>re-?\s?appointed|appointed|approved the (?:re-?\s?)?appointment of)\s+(?P<name>{NAME}){_DIN}\s*,?\s+{_AS}(?P<role>.{{3,110}}?){_ROLE_END}",
    re.I,
)
_PATTERNS = (_NOUN, _VERB_IN, _VERB_OUT, _CEASE)

_EFFECT_KEY = re.compile(r"\bw\.?\s?e\.?\s?f\.?\b|with effect from|\beffective\b|(?:close|closure) of business hours on|from the (?:close|closure) of", re.I)
_DATE_IN = re.compile(
    r"\d{1,2}(?:st|nd|rd|th)?[ .\-/]+[A-Za-z]{3,9}[ .\-/,’']*(?:19|20)?\d{2,4}"  # 23rd November 2026, 23-Nov-2026
    r"|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?:19|20)\d{2}"  # November 23, 2026
    r"|\d{1,2}[./-]\d{1,2}[./-](?:19|20)?\d{2}",  # 23.11.2026
)
_TERM = re.compile(r"for\s+a\s+(?:period|term)\s+of\s+(?P<n>\w+)(?:\s*\(\s*(?P<alt>\w+)\s*\))?\s+(?P<unit>years?|months?)", re.I)

_PROFILE_HEAD = re.compile(
    r"^[ \t]*(?:annexure[\s\-–—]*(?:[ivx]+|\d+|[a-z])?[\s:\-–—]*)?(?:brief\s+)?(?:profile|biography|background)\b[^\n]{0,90}$",
    re.I | re.M,
)
_PROFILE_STOP = re.compile(r"disclosure of relationships|\n\s*annexure\b|\n\s*\d+\.\s*\n|\n\s*(?:sr\.?|s\.?)\s*no\b", re.I)
_BOUNDARY = re.compile(r"\.(?=\s+[A-Z“\"‘(])")  # a full stop before a capital: a sentence end unless the word before it is an abbreviation
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "shri", "smt", "st", "no", "nos", "co", "ltd", "pvt", "inc", "jr", "sr", "vs", "viz",
    "etc", "approx", "dept", "govt", "w.e.f", "i.e", "e.g", "a.m", "p.m", "ca", "cs", "b.sc", "m.sc", "b.tech", "m.tech", "ph.d",
}
_NOT_A_PROFILE = re.compile(r"^(?:not applicable|n\.?a\.?|as provided in|as per|refer|please refer|details (?:are )?(?:given|provided|enclosed))", re.I)


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _tidy_role(role: str, company: str) -> str:
    """The role as the filing words it, without the trailing "of <the company>"."""
    role = squash(role)
    role = re.sub(r"(?<=\w)\((?=\w)", " (", role)  # "Director(designated as ...)"
    first = (company.split() or [""])[0]
    if first:
        role = re.sub(rf"\s+of\s+{re.escape(first)}\b.*$", "", role, flags=re.I)
    role = re.sub(r"\s+of\s+the\s+(?:company|bank|corporation)\b.*$", "", role, flags=re.I)
    role = re.sub(r"\s+(?:and\s+)?(?:also\s+)?as\s+(?:the\s+)?(?=Vice|Chair|Head|Non|Mana|Whole|Chief)", " and ", role)  # "Director and as Vice-Chairman"
    return role.strip(" ,.;:–-")


def kind_of(text: str) -> tuple[str, str] | None:
    """(kind, direction) from the words of a headline or sentence; re-appointment is tested before appointment."""
    for kind, direction, pattern in KINDS:
        if re.search(pattern, text, re.I):
            return kind, direction
    return None


def _event(match: re.Match[str], page: int, company: str, source: str) -> dict[str, Any]:
    word = match.group("kind")
    found = kind_of(word)
    kind, direction = found if found else ("change", "")
    if re.match(r"re-?\s?designation", word, re.I):
        kind, direction = "redesignation", "in"
    return {
        "kind": kind,
        "direction": direction,
        "name": squash(match.group("name")).rstrip("."),
        "din": match.groupdict().get("din"),
        "role": _tidy_role(match.group("role"), company),
        "page": page,
        "source": source,  # headline or filing
        "_end": match.end(),
    }


def _surname(name: str) -> str:
    return re.sub(rf"^{_TITLE}\s+", "", name).split()[-1].lower().strip(".")


def _bare(name: str) -> str:
    return re.sub(rf"^{_TITLE}\s+", "", name).strip()


def _complete(role: str) -> bool:
    return len(role) >= 3 and not role.endswith(("…", "..."))  # a headline cut short at a length limit is not a role


# A role never contains another person's name or a verb. If a "role" does, the pattern ran on into the next sentence
# (two lines of a filing squashed together), and it is dropped rather than shown.
_NOT_A_ROLE = re.compile(rf"(?-i:\b{_TITLE}\s+[A-Z])|\b(?:has|have|had|is|are|was|were|approved|informed?|intimat\w*|pursuant|considered|recommended)\b", re.I)


def _plausible(role: str) -> bool:
    return len(role) <= 110 and not _NOT_A_ROLE.search(role)


def find_events(headline: str, pages: dict[int, str], company: str) -> list[dict[str, Any]]:
    """The changes the filing announces: the headline's event first (it is the company's own one-line summary),
    completed by the sentence of the filing that states the same event, then any others the filing states."""
    head = squash(headline)
    head_event = None
    for pattern in _PATTERNS:
        match = pattern.search(head)
        if match:
            head_event = {**_event(match, 0, company, "headline"), "_end": -1}
            break

    filing: dict[str, dict[str, Any]] = {}
    for number in sorted(pages):
        text = squash(pages[number])
        for pattern in _PATTERNS:
            for match in pattern.finditer(text):
                event = {**_event(match, number, company, "filing"), "_text": text}
                if _complete(event["role"]) and _plausible(event["role"]):
                    filing.setdefault(_surname(event["name"]), event)

    events: list[dict[str, Any]] = []
    if head_event and len(head_event["role"]) >= 3 and _plausible(head_event["role"]):
        theirs = filing.pop(_surname(head_event["name"]), None)
        if theirs:  # the filing's sentence gives the page, the DIN, the date's anchor, and the role if the headline's was cut
            head_event.update(page=theirs["page"], din=theirs["din"] or head_event["din"], _text=theirs["_text"], _end=theirs["_end"])
            if not _complete(head_event["role"]):
                head_event["role"] = theirs["role"]
        if _complete(head_event["role"]):
            events.append(head_event)
    events.extend(filing.values())
    return events[:3]


def find_effective(text: str, start: int = 0) -> tuple[str, date] | None:
    """The first date that follows "effective", "w.e.f." or "with effect from" after `start`."""
    window = text[start : start + EVENT_WINDOW]
    for key in _EFFECT_KEY.finditer(window):
        chunk = window[key.end() : key.end() + 90]
        found = _DATE_IN.search(chunk)
        parsed = parse_date(found.group(0)) if found else None
        if found and parsed:
            return found.group(0).strip(" ,"), parsed
    return None


def find_term(text: str, start: int = 0) -> str | None:
    """"1 year" from "for a period of 1 (one) year", "5 years" from "five (5) years"."""
    match = _TERM.search(text[start : start + EVENT_WINDOW])
    if not match:
        return None
    count = next((w for w in (match.group("n"), match.group("alt")) if w and w.isdigit()), match.group("n"))
    return f"{count} {match.group('unit').lower()}"


def _sentences(text: str) -> list[str]:
    """Split at a full stop before a capital letter, but not after "Mr.", an initial ("V."), or "w.e.f."."""
    parts, start = [], 0
    for match in _BOUNDARY.finditer(text):
        token = re.search(r"([\w.’'\-]+)$", text[start : match.start()])
        word = token.group(1).lower().strip(".") if token else ""
        if word in _ABBREVIATIONS or len(word) == 1 or re.fullmatch(r"(?:[a-z]\.)+[a-z]", word):
            continue
        parts.append(text[start : match.end()].strip())
        start = match.end()
    if text[start:].strip():
        parts.append(text[start:].strip())
    return parts


def find_profile(pages: dict[int, str], surname: str | None = None) -> dict[str, Any] | None:
    """The first sentences of the filing's own profile section, word for word. With a surname, only a profile that
    names that person in its heading or its first lines counts, and a profile ends where the next one begins, so
    one appointee's profile is never shown for another."""
    for number in sorted(pages):
        text = pages[number]
        for head in _PROFILE_HEAD.finditer(text):
            rest = text[head.end() : head.end() + 1400]
            ends = [m.start() for m in (_PROFILE_STOP.search(rest), _PROFILE_HEAD.search(rest)) if m]
            body = squash(rest[: min(ends)] if ends else rest)
            if len(body) < 110 or _NOT_A_PROFILE.match(body):
                continue
            if surname and not re.search(rf"\b{re.escape(surname)}\b", squash(head.group(0) + " " + body[:200]), re.I):
                continue
            out, used = [], 0
            for sentence in _sentences(body)[:PROFILE_MAX_SENTENCES]:
                if out and used + len(sentence) > PROFILE_MAX_CHARS:
                    break
                out.append(sentence)
                used += len(sentence) + 1
            text_out = " ".join(out)
            if len(text_out) > PROFILE_MAX_CHARS:  # one sentence longer than the limit: cut at a word, and show that it was cut
                text_out = text_out[:PROFILE_MAX_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "…"
            if out:
                return {"text": text_out, "page": number, "source": "filing"}
    return None


def read_pdf_text(pdf: bytes) -> dict[int, str]:
    import pymupdf  # imported here so the API starts fast; only the pipeline reads PDFs

    document = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        return {i + 1: document[i].get_text("text") for i in range(document.page_count)}
    finally:
        document.close()


def _failed(reason: str) -> dict[str, Any]:
    return {"type": "management", "status": "failed", "reason": reason, "extractor": EXTRACTOR_VERSION}


def _anchor(name: str, pages: dict[int, str]) -> tuple[str, int, int | None]:
    """Where in the filing a person is written about, for a headline event that has no sentence of its own: the
    first place the full name appears after the cover letter's own heading. Returns (text, start, page)."""
    bare = re.escape(_bare(name))
    for number in sorted(pages):
        text = squash(pages[number])
        hits = list(re.finditer(bare, text, re.I))
        if hits:
            return text, hits[-1].start() if len(hits) > 1 else hits[0].start(), number
    return "", 0, None


def _person(event: dict[str, Any], pages: dict[int, str]) -> dict[str, Any]:
    text, start, page = event.pop("_text", None), event.pop("_end", 0), event["page"]
    if text is None or start < 0:  # the headline's event has no sentence of its own in the filing
        text, start, page = _anchor(event["name"], pages)
    effective = find_effective(text, max(start, 0)) if text else None
    term = find_term(text, max(start, 0)) if text else None
    profile = find_profile(pages, _surname(event["name"])) if event["direction"] == "in" else None
    return {
        "name": event["name"],
        "din": event["din"],
        "role": event["role"],
        "kind": event["kind"],
        "direction": event["direction"],
        "effective": {"date": effective[1].isoformat(), "text": effective[0]} if effective else None,
        "term": term,
        "profile": profile,
        "page": event["page"] or page,
    }


def build_card(
    pages: dict[int, str], *, headline: str, subject: str = "", company: str = "", source_url: str | None = None
) -> dict[str, Any]:
    """The card for one management-change filing, from its page texts."""
    if not any(squash(t) for t in pages.values()):
        return _failed("The filing has no readable text, so no details are shown. Open the filing to read it.")
    events = find_events(headline, pages, company)
    people = [_person(event, pages) for event in events]
    base = {"type": "management", "source": {"url": source_url, "pages": sorted({p["page"] for p in people if p["page"]})}, "extractor": EXTRACTOR_VERSION}
    if not people:
        # Nobody could be named. The kind of change may still be clear from the words, and is said so, nothing more.
        general = kind_of(f"{headline} {subject}") or next(iter(filter(None, (kind_of(squash(t)[:2500]) for t in pages.values()))), None)
        kind, direction = general or ("change", "")
        warning = "The person and role could not be read from this filing's text. Open the filing for the details."
        return {**base, "status": "partial", "kind": kind, "direction": direction, "people": [], "warnings": [warning]}
    return {**base, "status": "ok", "kind": people[0]["kind"], "direction": people[0]["direction"], "people": people, "warnings": []}


# ----------------------------------------------------------------------------------------- reading vs. the card
def read_filing(pdf: bytes, headline: str, subject: str, company: str) -> dict[str, Any]:
    """Read a filing into plain data that can be stored: the card's facts, which depend only on the file and the
    headline. Never raises for a bad PDF."""
    try:
        pages = read_pdf_text(pdf)
    except Exception as exc:  # corrupt or encrypted
        return {"card": _failed(f"The PDF could not be read ({type(exc).__name__}).")}
    return {"card": build_card(pages, headline=headline, subject=subject, company=company)}


PHRASES = {
    "appointment": "appointed",
    "re-appointment": "re-appointed",
    "redesignation": "redesignated",
    "resignation": "resigns as",
    "retirement": "to retire as",
    "cessation": "to cease as",
    "death": "demise:",
    "removal": "removed as",
}


def headline_for(card: dict[str, Any]) -> str | None:
    """"Dr. Madhu Sasidhar to cease as President & CEO - Hospitals Division, from 14 Nov", from the card's facts."""
    if card.get("status") != "ok" or not card["people"]:
        return None
    p = card["people"][0]
    phrase = PHRASES.get(p["kind"])
    if not phrase or not p["role"]:
        return None
    joiner = " " if phrase.endswith("as") or phrase.endswith(":") else " as "
    text = f"{p['name']} {phrase}{joiner}{p['role']}"
    if p["effective"]:
        day = date.fromisoformat(p["effective"]["date"])
        text += f", from {day.day} {day.strftime('%b')}"
    return text
