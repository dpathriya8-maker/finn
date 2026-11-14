"""Cut documents into chunks that keep their page, and pick out the forward-looking sentences by rule.

Nothing here calls a model. A chunk never crosses a page, because a citation is "document and page" and must be exact.
Only chunks that can matter go to a model, never a whole document (CLAUDE.md section 6).

Transcripts are read as turns: a line that is a speaker's label ("Rajeev Jain:", "Sh V Srikanth 00:00:01 - 00:09:00")
starts a new chunk, and the moderator's lines are left out of anything about what management said. A speaker is NOT
reported as the source of a quote: in real transcripts (Kaynes, for one) management's answers carry no label and follow
the analyst's labelled question, so the last label seen is often the wrong person. The source of a quote is the
document and the page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.pull.text import tidy_blocks

MAX_CHARS = 1100  # about a paragraph or two: enough to quote from, small enough to send many
MIN_CHARS = 80

_TITLES = {"mr", "mrs", "ms", "miss", "dr", "sh", "shri", "smt", "prof", "capt", "col", "ca", "cs"}
_NOT_NAMES = re.compile(
    r"\b(?:limited|ltd|cin|office|participants?|presentation|audio|link|encl\w*|subject|sub|transcript|management|page|note|source|slide|"
    r"figure|table|question|answer|speaker|agenda|disclaimer|regd|registered|website|email|tel|telephone|phone|mobile|fax|dear|ladies|ref|date|"
    r"scrip|symbol|isin|bse|nse|corporate|id|no|duration|contact|din|gst|pan|time|venue|call|conference|earnings|quarter|results)\b",
    re.I,
)
_LABEL = re.compile(
    r"^(?P<name>(?:(?:Mr|Mrs|Ms|Miss|Dr|Sh|Shri|Smt|Prof|Capt|Col)\.?\s+)?[A-Z][A-Za-z.'’\-]+(?:\s+[A-Z][A-Za-z.'’\-]+){0,4})\s*(?::|(?=\s\d{1,2}:\d{2}:\d{2}))\s*(?P<rest>.*)$"
)
_TIMECODE = re.compile(r"^\s*\d{1,2}:\d{2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}:\d{2}\s*(?:\([^)]*\))?\s*")


@dataclass(frozen=True)
class Chunk:
    doc: str  # document id ("d1")
    page: int  # the PDF's own page number, from 1
    text: str
    moderator: bool = False  # the call operator's words: never management's


def _label(line: str) -> tuple[str, str] | None:
    """(speaker, the rest of the line) if this line begins a turn, else None."""
    stripped = line.strip()
    if not stripped or len(stripped) > 160:
        return None
    match = _LABEL.match(stripped)
    if not match:
        return None
    name = re.sub(r"\s+", " ", match.group("name")).strip(" .")
    if _NOT_NAMES.search(name) or len(name) > 48:
        return None
    if name.isupper() and name.lower() != "moderator":  # an ALL-CAPS label is a heading ("MANAGEMENT:"), unless it is the operator
        return None
    return ("Moderator" if name.lower() == "moderator" else name), _TIMECODE.sub("", match.group("rest"))


def _split_long(paragraph: str) -> list[str]:
    """Break a paragraph longer than MAX_CHARS at sentence ends."""
    if len(paragraph) <= MAX_CHARS:
        return [paragraph]
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", paragraph):
        if current and len(current) + len(sentence) + 1 > MAX_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _logical_lines(page: str) -> list[tuple[str, str | None]]:
    """A page as (text, label) pairs: wrapped lines joined into paragraphs, except that a speaker's label starts its own entry."""
    out: list[tuple[str, str | None]] = []
    for block in tidy_blocks(page):
        current: list[str] = []
        for line in block:
            found = _label(line)
            if found:
                if current:
                    out.append((" ".join(current), None))
                    current = []
                out.append((found[1], found[0]))
            else:
                current.append(line)
        if current:
            out.append((" ".join(current), None))
    return out


def chunk_pages(doc_id: str, pages: list[str]) -> list[Chunk]:
    """Chunks of about one to two paragraphs. A new speaker's label starts a new chunk; a chunk never crosses a page."""
    chunks: list[Chunk] = []
    operator = False
    for number, page in enumerate(pages, start=1):
        buffer, buffer_operator = "", operator

        def flush() -> None:
            nonlocal buffer
            if buffer.strip():
                chunks.append(Chunk(doc_id, number, buffer.strip(), buffer_operator))
            buffer = ""

        for text, label in _logical_lines(page):
            if label is not None:
                flush()
                operator = buffer_operator = label == "Moderator"
            for piece in _split_long(text) if text else []:
                if buffer and len(buffer) + len(piece) + 1 > MAX_CHARS:
                    flush()
                    buffer_operator = operator
                buffer = f"{buffer} {piece}".strip()
        flush()
    return [c for c in chunks if len(c.text) >= MIN_CHARS]


# --------------------------------------------------------------------------------------- forward-looking sentences
_FORWARD = re.compile(
    r"\b(?:we\s+(?:will|shall|expect|plan|aim|intend|anticipate|are\s+(?:targeting|planning|confident|on\s+track|looking\s+to|going\s+to)|should|are\s+committed|have\s+committed|said\s+we\s+will)"
    r"|(?:is|are)\s+(?:expected|likely|on\s+track|scheduled|planned)\s+to|will\s+be\s+(?:launched|commissioned|completed|ready|operational|live|listed)"
    r"|going\s+forward|over\s+the\s+next|in\s+the\s+(?:next|coming)\s+(?:\w+\s+)?(?:quarters?|years?|months?)|guidance|outlook\s+(?:for|remains)"
    r"|target(?:ed|ing|s)?\b|aspiration|roadmap|ramp[- ]?up|commission(?:ed|ing)|launch(?:ing)?\s+(?:in|by)|by\s+(?:the\s+end\s+of\s+)?(?:fy|q[1-4]|march|june|september|december|next\s+year|next\s+quarter))",
    re.I,
)
_ANCHOR = re.compile(r"(?:\bfy\s?'?\d{2,4}\b|\bq[1-4]\b|\b20[2-3]\d\b|\d[\d,.]*\s?(?:%|per\s?cent|crore|cr\b|lakh|bn\b|billion|million|mw|gw|x\b|bps|basis\s+points)|\brs\.?\s?\d|\binr\s?\d|₹\s?\d)", re.I)
_QUESTIONISH = re.compile(r"(?:\?|^\s*(?:can|could|would|what|how|why|when|do|does|did|is|are|will)\s+you\b|\bmy\s+(?:first|second|third)\s+question\b|\bthank\s+you\b.*\bquestion\b)", re.I)
_EXTERNAL = re.compile(r"\b(?:IEA|OPEC|EIA|IMF|World\s+Bank|according\s+to|forecast\s+of|projection\s+(?:is|from|of)|consensus)\b")  # somebody else's forecast
# An analyst, not management: a question put as a statement ("my question is on", "that you mentioned"), or a sentence that
# talks about "you" more than "we" (management speaks for the company in the first person).
_ANALYST = re.compile(
    r"\bmy\s+(?:first\s+|second\s+|third\s+|next\s+|last\s+)?question\b|\bi\s+(?:just\s+)?(?:want|wanted)\s+to\s+(?:understand|ask|know|clarify|check)\b"
    r"|\byou\s+(?:mentioned|said|indicated|guided|highlighted|talked\s+about|spoke|are\s+(?:still\s+)?(?:looking|expecting|guiding))\b|^\s*(?:and\s+)?sir\b|\b(?:can|could|would)\s+you\b",
    re.I,
)
_YOU, _WE = re.compile(r"\b(?:you|your|yours)\b", re.I), re.compile(r"\b(?:we|our|ours|us)\b", re.I)


def _is_analyst(sentence: str) -> bool:
    return bool(_ANALYST.search(sentence)) or len(_YOU.findall(sentence)) > len(_WE.findall(sentence))
_BOILERPLATE = re.compile(r"(?:forward[- ]looking\s+statements?|safe\s+harbou?r|no\s+assurance|risks\s+and\s+uncertainties|disclaimer)", re.I)
_SPLIT_SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(₹])")

MIN_SENTENCE = 60
MAX_SENTENCE = 380


@dataclass(frozen=True)
class Statement:
    doc: str
    page: int
    text: str  # one sentence, exactly as in the document, tidied
    score: int


def forward_statements(chunks: list[Chunk], *, limit: int = 12) -> list[Statement]:
    """Sentences where management looks ahead, found by rule: a forward verb (we will, we expect, targeting, by FY27 ...)
    plus a number or a date, from the speakers and not from the moderator, a question, or somebody else's forecast.
    Ranked by how many concrete anchors they carry. A list to read, not a verdict: whether anything was delivered is a
    separate question."""
    found: list[Statement] = []
    for chunk in chunks:
        if chunk.moderator:
            continue
        for sentence in _SPLIT_SENTENCES.split(chunk.text):
            s = sentence.strip()
            if not (MIN_SENTENCE <= len(s) <= MAX_SENTENCE) or _QUESTIONISH.search(s) or _BOILERPLATE.search(s) or _EXTERNAL.search(s) or _is_analyst(s):
                continue
            forward, anchors = _FORWARD.findall(s), _ANCHOR.findall(s)
            if forward and anchors:
                found.append(Statement(chunk.doc, chunk.page, s, 2 * len(forward) + len(anchors)))
    seen: set[str] = set()
    ranked = []
    for item in sorted(found, key=lambda s: (-s.score, s.page)):
        key = re.sub(r"\W+", "", item.text.lower())[:80]
        if key not in seen:
            seen.add(key)
            ranked.append(item)
    return sorted(ranked[:limit], key=lambda s: (s.page, -s.score))
