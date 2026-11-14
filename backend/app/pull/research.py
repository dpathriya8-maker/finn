"""Research on one company, from its own filings only: the documents, what management said about the future (found by
rule, no model), and, when a model is configured, a Promise Tracker with verified quotes and verdicts.

The record says what ran. `status` is "ready" (promises judged), "statements_only" (documents read, no model ran, and
`model.reason` says why) or "no_documents". Nothing is filled in to make a record look complete.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable

from app.core import llm
from app.core.timeutil import now_ist
from app.pull import promises as pr
from app.pull.chunk import Chunk, chunk_pages, forward_statements
from app.pull.ingest import Corpus, IngestSources, NoDocuments, ingest
from app.pull.retrieve import Index
from app.pull.text import strip_repeated_lines

SCHEMA = 1
STATEMENTS_PER_CALL = 6


class Recorder:
    """Wraps a router and remembers what it did, so the record can state which models ran and how many calls were cached."""

    def __init__(self, router: pr.Router):
        self.router, self.calls = router, []

    def complete_json(self, tier: str, system: str, prompt: str, **kwargs: Any) -> Any:
        result = self.router.complete_json(tier, system, prompt, **kwargs)
        self.calls.append(result)
        return result

    def summary(self) -> dict[str, Any]:
        return {
            "calls": len(self.calls),
            "cache_hits": sum(bool(c.cached) for c in self.calls),
            "tokens_in": sum(c.tokens_in for c in self.calls),
            "tokens_out": sum(c.tokens_out for c in self.calls),
            "models": sorted({f"{c.provider}:{c.model}" for c in self.calls}),
        }


def chunks_of(corpus: Corpus) -> dict[str, list[Chunk]]:
    return {d.id: chunk_pages(d.id, strip_repeated_lines(d.pages)) for d in corpus.documents}


def _document_dict(d: Any) -> dict[str, Any]:
    return {"id": d.id, "kind": d.kind, "title": d.title, "period": d.period, "date": d.date, "url": d.url, "pages": len(d.pages), "bytes": d.bytes, "sha256": d.sha256}


def _empty(symbol: str, name: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "symbol": symbol, "name": name, "generated_at": now_ist().isoformat(timespec="seconds"), "status": status, "reason": reason,
        "model": {"ran": False, "reason": reason}, "documents": [], "warnings": [], "promises": [], "scorecard": None, "statements": [],
    }


def build_record(
    corpus: Corpus,
    name: str,
    *,
    router: pr.Router | None = None,
    progress: Callable[[str], None] = lambda _m: None,
) -> dict[str, Any]:
    """The record for a company whose documents have been read. `router` None means no model is configured: the record
    is then documents and statements only, and says so."""
    chunks = chunks_of(corpus)
    transcripts = [d for d in corpus.documents if d.kind == "transcript"]
    statements = [
        {"doc": s.doc, "quarter": d.period, "page": s.page, "text": s.text}
        for d in transcripts
        for s in forward_statements(chunks[d.id], limit=STATEMENTS_PER_CALL)
    ]
    record: dict[str, Any] = {
        "schema": SCHEMA, "symbol": corpus.symbol, "name": corpus.name or name, "generated_at": now_ist().isoformat(timespec="seconds"),
        "status": "statements_only", "reason": None, "model": {"ran": False, "reason": "No model is configured."},
        "documents": [_document_dict(d) for d in corpus.documents], "warnings": corpus.warnings,
        "promises": [], "scorecard": None, "statements": statements,
    }
    if router is None:
        return record
    if len(transcripts) < 2:
        record["model"] = {"ran": False, "reason": "A promise needs a later call to be checked against, and fewer than two transcripts were found."}
        return record

    recorder = Recorder(router)
    try:
        progress("Extracting promises and checking them against later calls")
        promises = pr.build_tracker(recorder, company=corpus.name or name, calls=[(d.id, d.period or "", chunks[d.id]) for d in transcripts])
    except llm.LLMUnavailable as exc:
        record["model"] = {"ran": False, "reason": exc.reason, **recorder.summary()}
        return record
    record.update(
        status="ready", promises=[pr.to_dict(p) for p in promises], scorecard=pr.scorecard(promises),
        model={"ran": True, "reason": None, **recorder.summary()},
    )
    return record


def research(
    symbol: str,
    name: str,
    *,
    sources: IngestSources | None = None,
    router: pr.Router | None = None,
    progress: Callable[[str], None] = lambda _m: None,
) -> dict[str, Any]:
    """Read a company's documents and build its record. A company with nothing to read gets a record that says so."""
    try:
        corpus = ingest(symbol, sources, progress=progress)
    except NoDocuments as exc:
        return _empty(symbol, name, "no_documents", exc.reason)
    return build_record(corpus, name, router=router, progress=progress)


# ------------------------------------------------------------------------------------------------ for "Ask the documents"
_MEMO: OrderedDict[str, tuple[Index, Corpus]] = OrderedDict()
MEMO_SIZE = 3  # a corpus is a few hundred KB of text; three keep a small instance well inside its memory


def corpus_index(symbol: str, sources: IngestSources | None = None) -> tuple[Index, Corpus]:
    """The searchable index of a company's documents (built from the cached pages, so it costs no download after the first)."""
    if symbol in _MEMO:
        _MEMO.move_to_end(symbol)
        return _MEMO[symbol]
    corpus = ingest(symbol, sources)
    index = Index([c for chunks in chunks_of(corpus).values() for c in chunks])
    _MEMO[symbol] = (index, corpus)
    while len(_MEMO) > MEMO_SIZE:
        _MEMO.popitem(last=False)
    return _MEMO[symbol]
