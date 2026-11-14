"""Find the chunks of the documents that bear on a question: BM25, in plain Python, no model and no service.

Used twice: to pick the later excerpts a promise is judged against, and to answer "Ask the documents". Because it is
ranking by the words actually present, a question about something the documents never mention scores nothing, which is
how "Not found in the documents" is decided before any model is asked.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.pull.chunk import Chunk
from app.pull.text import normalise

_STOP = frozenset(
    "a an and are as at be been but by can could did do does for from had has have how i if in into is it its of on or our so than that the their "
    "them then there these they this to up was we were what when where which who whom why will with would you your about any all also any did say said "
    "tell told management company companies please".split()
)
_TOKEN = re.compile(r"[a-z0-9]+(?:[.'\-][a-z0-9]+)*")


def tokens(text: str) -> list[str]:
    """Lower-cased words and numbers, stop words dropped, plurals folded: "capacities" and "capacity" meet."""
    out = []
    for word in _TOKEN.findall(normalise(text).lower()):
        if word in _STOP or len(word) < 2:
            continue
        if len(word) > 4 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        out.append(word)
    return out


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    coverage: float  # the share of the question's distinct words that this chunk contains


class Index:
    def __init__(self, chunks: list[Chunk], *, k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.docs = [Counter(tokens(c.text)) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        frequency: Counter[str] = Counter()
        for d in self.docs:
            frequency.update(d.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in frequency.items()}

    def search(self, query: str, k: int = 8, *, docs: set[str] | None = None) -> list[Hit]:
        """The best chunks, best first. Only chunks that contain at least one of the question's words are returned."""
        terms = list(dict.fromkeys(tokens(query)))
        if not terms or not self.chunks:
            return []
        hits: list[Hit] = []
        for chunk, counts, length in zip(self.chunks, self.docs, self.lengths):
            if docs is not None and chunk.doc not in docs:
                continue
            matched = [t for t in terms if counts.get(t)]
            if not matched:
                continue
            score = 0.0
            for t in matched:
                tf = counts[t]
                score += self.idf.get(t, 0.0) * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / (self.avg or 1)))
            hits.append(Hit(chunk, score, len(matched) / len(terms)))
        hits.sort(key=lambda h: (-h.score, h.chunk.page))
        return hits[:k]
