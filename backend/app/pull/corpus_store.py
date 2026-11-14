"""Save and load a company's documents (their page text) as one compressed file, so the demo companies' research and
"Ask the documents" work without reaching the exchanges at request time. The exchanges are only proven reachable from a
home connection; a deployed server may be blocked, and a demo must not depend on that.

The text in these files is what the company itself filed. Nothing is edited, and the record that cites it carries each
document's URL and SHA-256, so a reader can check it against the original.
"""
from __future__ import annotations

import gzip
import json
import os
import tempfile
from pathlib import Path

from app.core.settings import REPO_ROOT
from app.pull.ingest import Corpus, Document

DEFAULT_DIR = REPO_ROOT / "backend" / "data" / "corpus"
SCHEMA = 1


def path_for(symbol: str, directory: Path) -> Path:
    return directory / f"{symbol}.json.gz"


def save(corpus: Corpus, directory: Path) -> Path:
    """Write atomically, so a crash never leaves half a file."""
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA, "symbol": corpus.symbol, "name": corpus.name, "warnings": corpus.warnings,
        "documents": [{"id": d.id, "kind": d.kind, "title": d.title, "period": d.period, "date": d.date, "url": d.url, "bytes": d.bytes, "sha256": d.sha256, "pages": d.pages} for d in corpus.documents],
    }
    target = path_for(corpus.symbol, directory)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as handle:  # mtime 0: the same input gives the same bytes
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target


def load(symbol: str, directory: Path) -> Corpus | None:
    """The saved documents, or None if there are none or the file cannot be read (it is then simply fetched again)."""
    try:
        with gzip.open(path_for(symbol, directory), "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        if data.get("schema") != SCHEMA:
            return None
        return Corpus(
            symbol=data["symbol"], name=data["name"], warnings=list(data.get("warnings", [])),
            documents=[Document(**{**d, "pages": list(d["pages"])}) for d in data["documents"]],
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None
