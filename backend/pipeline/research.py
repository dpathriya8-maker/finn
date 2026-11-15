"""Precompute research for the demo companies into frontend/public/data/research/*.json, and keep their documents with
the app so "Ask the documents" works without reaching the exchanges at request time.

    python -m pipeline.research                      # the research companies in config/research.json
    python -m pipeline.research --symbols HAL NAUKRI # just these (any NSE symbol)
    python -m pipeline.research --offline            # rebuild records from the saved documents, no downloads

With GEMINI_API_KEY (or GROQ_API_KEY) and LLM_CHEAP_MODEL in .env, the Promise Tracker is built with verdicts. Without a
model the record holds the documents and the forward-looking statements found by rule, and says so. Re-running without a
key never replaces a record that already has verdicts.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.core import llm
from app.core.cache import default_cache
from app.core.settings import REPO_ROOT
from app.core.timeutil import now_ist
from app.pull import corpus_store
from app.pull.ingest import IngestSources, NoDocuments, ingest
from app.pull.research import SCHEMA, build_record
from pipeline.run import write_json

DEFAULT_OUT = REPO_ROOT / "frontend" / "public" / "data" / "research"


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def load_companies() -> list[dict[str, str]]:
    return json.loads((REPO_ROOT / "config" / "research.json").read_text(encoding="utf-8"))["companies"]


def _previous(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_index(companies: list[dict[str, str]], out_dir: Path) -> None:
    """index.json lists every research company that has a record: all of the configured ones, plus any other symbol just
    researched. A run for one symbol (`--symbols NAUKRI`) must never shrink the list the Research and Interested screens read."""
    configured = load_companies()
    listed = [*configured, *[c for c in companies if c["symbol"] not in {k["symbol"] for k in configured}]]
    index = [
        {"symbol": r["symbol"], "name": r["name"], "status": r["status"], "documents": len(r["documents"]), "generated_at": r["generated_at"]}
        for c in listed if (r := _previous(out_dir / f"{c['symbol']}.json"))
    ]
    write_json(out_dir / "index.json", {"schema": SCHEMA, "generated_at": now_ist().isoformat(timespec="seconds"), "companies": index}, indent=1)


def run(
    companies: list[dict[str, str]],
    *,
    out_dir: Path = DEFAULT_OUT,
    corpus_dir: Path = corpus_store.DEFAULT_DIR,
    sources: IngestSources | None = None,
    router: Any = "auto",
    offline: bool = False,
    log: Callable[[str], None] = print,
) -> Report:
    report = Report()
    if router == "auto":
        router = llm.Router(cache=default_cache()) if llm.available("cheap") else None
    log("Model: " + ("configured, the Promise Tracker will be built" if router is not None else "none configured, records will hold documents and statements only"))
    for company in companies:
        symbol, name = company["symbol"], company.get("name", company["symbol"])
        path = out_dir / f"{symbol}.json"
        try:
            if offline:
                corpus = corpus_store.load(symbol, corpus_dir)
                if corpus is None:
                    raise NoDocuments("There is no saved copy of this company's documents.")
            else:
                corpus = ingest(symbol, sources or IngestSources(cache=default_cache()), progress=lambda m, s=symbol: log(f"  {s}: {m}"))
                corpus_store.save(corpus, corpus_dir)
        except NoDocuments as exc:
            report.failed[symbol] = exc.reason
            log(f"{symbol:11s} no documents: {exc.reason}")
            continue
        except Exception as exc:  # one company must not stop the rest
            report.failed[symbol] = f"{type(exc).__name__}: {str(exc)[:160]}"
            log(f"{symbol:11s} FAILED {report.failed[symbol]}")
            continue
        record = build_record(corpus, name, router=router, progress=lambda m, s=symbol: log(f"  {s}: {m}"))
        earlier = _previous(path)
        if earlier.get("status") == "ready" and record["status"] != "ready":
            report.kept.append(symbol)
            log(f"{symbol:11s} kept the earlier record, which has verdicts; this run had no model ({record['model'].get('reason')})")
            continue
        write_json(path, record)
        report.written.append(symbol)
        docs = ", ".join(f"{d['period']}" for d in record["documents"])
        log(f"{symbol:11s} {record['status']:16s} {len(record['documents'])} documents ({docs}), {len(record['statements'])} statements, {len(record['promises'])} promises")
    write_index(companies, out_dir)
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Precompute the research the app shows.")
    parser.add_argument("--symbols", nargs="*", help="only these NSE symbols (any symbol, not only the demo companies)")
    parser.add_argument("--offline", action="store_true", help="rebuild from the saved documents, no downloads")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    known = {c["symbol"]: c for c in load_companies()}
    companies = [known.get(s.upper(), {"symbol": s.upper(), "name": s.upper()}) for s in args.symbols] if args.symbols else list(known.values())
    report = run(companies, out_dir=args.out, offline=args.offline)
    print(f"\n{len(report.written)} written, {len(report.kept)} kept, {len(report.failed)} failed -> {args.out}")
    return 0 if report.written or report.kept else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
