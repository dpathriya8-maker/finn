"""A small SQLite cache for work that is slow or costly to repeat: what was read out of a filing, and (from Step 9)
what a model said about a document. The same input never costs twice.

Keys are strings and values are JSON. For model calls the key is sha256(document bytes + prompt version + model),
which `llm_key` builds. The cache is a convenience and never a dependency: if the file cannot be opened or a read
fails, the caller simply does the work again, and a failed write is dropped silently.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.core.settings import REPO_ROOT

DEFAULT_PATH = REPO_ROOT / "backend" / ".cache" / "finn.sqlite"  # git-ignored
_SCHEMA = "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, created_at REAL NOT NULL)"


def digest_key(*parts: bytes | str) -> str:
    """sha256 over the parts. Each part is length-prefixed so ("ab", "c") and ("a", "bc") cannot collide."""
    h = hashlib.sha256()
    for part in parts:
        raw = part if isinstance(part, bytes) else part.encode("utf-8")
        h.update(len(raw).to_bytes(8, "big"))
        h.update(raw)
    return h.hexdigest()


def llm_key(doc: bytes | str, prompt_version: str, model: str) -> str:
    """The cache key for a model call: the same document, prompt and model always map to the same key."""
    return digest_key(doc, prompt_version, model)


class Cache:
    """Key-value store on SQLite. Pass ":memory:" for a throwaway cache (tests)."""

    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = str(path)
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None
        try:
            if self.path != ":memory:":
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
            db.execute(_SCHEMA)
            db.commit()
            self._db = db
        except (sqlite3.Error, OSError):
            self._db = None  # unusable: behaves as an always-empty cache

    @property
    def usable(self) -> bool:
        return self._db is not None

    def get(self, key: str) -> Any | None:
        if self._db is None:
            return None
        try:
            with self._lock:
                row = self._db.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
            return json.loads(row[0]) if row else None
        except (sqlite3.Error, ValueError):
            return None

    def set(self, key: str, value: Any) -> bool:
        """Store a JSON-serialisable value. Returns False when it could not be stored."""
        if self._db is None:
            return False
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            with self._lock:
                self._db.execute("INSERT OR REPLACE INTO kv (key, value, created_at) VALUES (?, ?, ?)", (key, text, time.time()))
                self._db.commit()
            return True
        except (sqlite3.Error, TypeError, ValueError):
            return False

    def delete(self, key: str) -> None:
        if self._db is None:
            return
        try:
            with self._lock:
                self._db.execute("DELETE FROM kv WHERE key = ?", (key,))
                self._db.commit()
        except sqlite3.Error:
            pass

    def __len__(self) -> int:
        if self._db is None:
            return 0
        try:
            with self._lock:
                return int(self._db.execute("SELECT COUNT(*) FROM kv").fetchone()[0])
        except sqlite3.Error:
            return 0

    def close(self) -> None:
        if self._db is not None:
            with self._lock:
                self._db.close()
            self._db = None


def default_cache() -> Cache:
    """The on-disk cache, at CACHE_PATH if set, else backend/.cache/finn.sqlite."""
    return Cache(os.getenv("CACHE_PATH") or DEFAULT_PATH)
