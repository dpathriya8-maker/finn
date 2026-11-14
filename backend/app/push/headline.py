"""One-line headline for a card, built by rules, with no model.

Exchange subjects are mostly boilerplate ("Announcement under Regulation 30 (LODR)-Credit Rating") and
often shouted in Title Case; the useful words are usually in the body. This picks the more informative of
the two, tidies the case and trims to one line. A model-written summary can replace it later for the
few filings that deserve one; this is what every filing gets for free.
"""
from __future__ import annotations

import re

MAX_LEN = 140

_PREFIXES = [
    re.compile(p, re.I)
    for p in (
        r"^announcement under regulation \d+[a-z]? \(lodr\)\s*[-–:]\s*",
        r"^announcement under regulation \d+[a-z]?(?:\(\w+\))* of (?:the )?sebi \(listing obligations and disclosure requirements\) regulations,? \d{4}\s*[-–:]?\s*",
        r"^(?:disclosure|intimation) under regulation \d+[a-z]?(?:\(\w+\))*[^-–:]{0,110}[-–:]\s*",
        r"^board meeting outcome for\s*",
        r"^results\s*[-–]\s*",
    )
]
_GENERIC = {
    "general", "updates", "general updates", "credit rating", "newspaper publication", "press release / media release",
    "press release", "analyst / investor meet", "analyst / investor meet - intimation", "analyst / investor meet - outcome",
    "investor presentation", "outcome of board meeting", "outcome", "intimation", "earnings call transcript",
    "board meeting", "agm", "egm", "postal ballot", "closure of trading window", "trading window", "newspaper advertisement",
}
_STOP = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with", "under", "its"}
_ACRONYMS = {
    "LODR", "SEBI", "AGM", "EGM", "QIP", "NCD", "NCDS", "ESOP", "ESPS", "CFO", "CEO", "CMD", "MD", "NSE", "BSE", "IPO",
    "PIT", "SAST", "RBI", "NCLT", "NBFC", "GST", "FY", "LLP", "USD", "INR", "AOA", "MOA", "ECB", "KMP", "SMP", "PNB", "SBI",
}


def strip_boilerplate(subject: str) -> str:
    text = re.sub(r"\s+", " ", subject or "").strip()
    for pattern in _PREFIXES:
        text = pattern.sub("", text, count=1)
    return text.strip(" -–:")


def tidy_case(text: str) -> str:
    """ALL CAPS becomes Title Case; in Title Case, small words go lower case ("For The Quarter" -> "for the quarter")."""
    words = text.split(" ")
    alpha = [w for w in words if re.match(r"[A-Za-z]", w)]
    if len(alpha) < 3:
        return text
    if all(w == w.upper() for w in alpha if len(re.sub(r"[^A-Za-z]", "", w)) > 1):
        words = [w if re.sub(r"[^A-Za-z]", "", w).upper() in _ACRONYMS or re.search(r"\d", w) else w.capitalize() for w in words]
    capped = sum(1 for w in alpha if w[0].isupper()) / len(alpha)
    if capped >= 0.7:
        words = [w.lower() if i > 0 and w.lower() in _STOP else w for i, w in enumerate(words)]
    return _ORDINAL.sub(lambda m: m.group(1).lower(), " ".join(words))  # "12TH" and "30Th" become "12th", "30th"


_NSE_LEAD = re.compile(r"^.{1,110}?\bhas informed (?:the )?exchange\s*(?:about|regarding|that|-)?\s*[-:]?\s*", re.I)
_NOISE_BODY = re.compile(
    r"^(?:please|kindly)\b.{0,40}\b(?:find|refer|see|note)\b|^pfa\b|^enclosed\b|^attached\b|^as per (?:the )?(?:annexure|attach\w*|enclosed)",
    re.I,
)
_ORDINAL = re.compile(r"(?<=\d)(st|nd|rd|th)\b", re.I)
_RUPEE = re.compile(r"(?<![\w?])\?(?=\d)")  # BSE sends the rupee sign as "?": "face value ?10/-"
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "shri", "smt", "prof", "ltd", "pvt", "no", "vs", "m/s", "st", "inc", "co", "i.e", "e.g"}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def first_sentence(body: str) -> str:
    text = re.sub(r"\s+", " ", (body or "").replace("''", "'")).strip()
    text = _RUPEE.sub("₹", text)
    text = _NSE_LEAD.sub("", text, count=1) if _NSE_LEAD.match(text) else text
    for match in _SENTENCE_END.finditer(text):
        last_word = text[: match.start()].rsplit(" ", 1)[-1].rstrip(".!?").lower()
        if last_word not in _ABBREVIATIONS and len(last_word) > 1:  # "Mr. Rao" and "V. Rao" do not end a sentence
            return text[: match.start()]
    return text


def _clip(text: str) -> str:
    if len(text) <= MAX_LEN:
        return text
    cut = text[:MAX_LEN].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return cut + "…"


_ONLY_BOILERPLATE = re.compile(r"^(?:disclosure|announcement|intimation) under regulation\b", re.I)
_GLUED_PAREN = re.compile(r"(?<=[a-z])\((?=[a-z]{3,})")  # "Director(designated as ...)" as an exchange sends it; not "Section 12A(b)" or "Rule 3(a)"


def _is_generic(subject: str) -> bool:
    return len(subject) < 25 or subject.lower().rstrip(".") in _GENERIC or bool(_ONLY_BOILERPLATE.match(subject))


def make_headline(subject: str, body: str) -> str:
    """Whichever of subject and body says more: the subject when it is specific, the body when the subject is
    only a label. A body that just says "please find the enclosed file" is ignored."""
    subj = strip_boilerplate(subject)
    snippet = first_sentence(body)
    if len(snippet) < 70 and _NOISE_BODY.search(snippet):
        snippet = ""
    same = snippet.lower().rstrip(".") == subj.lower().rstrip(".") or snippet.lower() in subj.lower()
    if not snippet or same or (len(snippet) < 20 and subj):
        chosen = subj or snippet
    elif _is_generic(subj):
        chosen = snippet
    else:
        chosen = subj
    chosen = _GLUED_PAREN.sub(" (", tidy_case(chosen)).strip()
    if chosen and chosen[0].islower():
        chosen = chosen[0].upper() + chosen[1:]
    return _clip(chosen) or "Filing"
