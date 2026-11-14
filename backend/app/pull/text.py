"""Text clean-up and the verbatim check that every quote shown to a reader must pass.

A quote is shown only if it appears word for word in the page it is credited to. "Word for word" tolerates what a PDF
does to text and nothing else: line breaks, runs of spaces, a hyphen broken across a line ("year-on-\\nyear"),
typographic quotes and dashes, ligatures. A reworded quote, a changed number or a different name does not match.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

_QUOTES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"', "–": "-", "—": "-", "−": "-", " ": " ", "​": ""})
_PRIVATE_USE = re.compile(r"[-�]")  # bullets and symbols a PDF's font maps to private codes
_HYPHEN_BREAK = re.compile(r"(?<=\w)-[ \t]*\n[ \t]*(?=\w)")


def normalise(text: str) -> str:
    """For comparing: NFKC (ligatures, width), plain quotes and dashes, hyphen-linebreaks joined, whitespace collapsed."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    text = _PRIVATE_USE.sub(" ", text)
    text = _HYPHEN_BREAK.sub("-", text)
    return re.sub(r"\s+", " ", text).strip()


def quote_is_in(quote: str, text: str) -> bool:
    """True if the quote is in the text word for word, after the tolerated clean-up above. Case counts."""
    wanted = normalise(quote).strip(" .\"'")
    return len(wanted) >= 12 and wanted in normalise(text)


def strip_repeated_lines(pages: list[str]) -> list[str]:
    """Remove what repeats on most pages (a company name, a date, "Page 4 of 19", a bare page number): it would
    otherwise sit in the middle of sentences that run across a page."""
    if not pages:
        return pages
    seen: Counter[str] = Counter()
    for page in pages:
        seen.update({normalise(line) for line in page.splitlines() if 0 < len(line.strip()) < 90})
    limit = max(3, int(len(pages) * 0.4))
    noise = {line for line, count in seen.items() if count >= limit}
    out = []
    for page in pages:
        kept = [
            line
            for line in page.splitlines()
            if normalise(line) not in noise and not re.fullmatch(r"\s*(?:page\s+)?\d{1,3}(?:\s+of\s+\d{1,3})?\s*", line, re.I)
        ]
        out.append("\n".join(kept).strip())
    return out


def tidy(text: str) -> str:
    """A page's text as readable paragraphs: hyphen-linebreaks joined, line wraps removed, private-use bullets gone."""
    text = _PRIVATE_USE.sub(" ", unicodedata.normalize("NFKC", text))
    text = _HYPHEN_BREAK.sub("-", text)
    paragraphs = [re.sub(r"[ \t]*\n[ \t]*", " ", block).strip() for block in re.split(r"\n\s*\n", text)]
    return "\n".join(p for p in (re.sub(r"[ \t]+", " ", p) for p in paragraphs) if p)


def tidy_blocks(text: str) -> list[list[str]]:
    """A page as blocks (split on blank lines) of its lines, with hyphen-linebreaks joined and private-use bullets
    gone. The chunker joins the lines itself, because a speaker's label can sit in the middle of a block."""
    text = _PRIVATE_USE.sub(" ", unicodedata.normalize("NFKC", text))
    text = _HYPHEN_BREAK.sub("-", text)
    blocks = [[re.sub(r"[ \t]+", " ", line).strip() for line in block.splitlines() if line.strip()] for block in re.split(r"\n\s*\n", text)]
    return [b for b in blocks if b]
