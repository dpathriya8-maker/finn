"""Serving research: finished records (shipped with the app or computed earlier), background jobs for fresh ones with a
visible stage, a daily cap on fresh work, and "Ask the documents".

Fresh research downloads and reads several PDFs and may call a model, so it runs in the background and the app polls
for it. Cached research is unlimited; only fresh work counts against DAILY_FRESH_RESEARCH_CAP, which protects the free
model quota. The count lives in the cache, so a restart of a free instance resets it: it is a guard, not an audit.
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from app.core import llm
from app.core.cache import Cache, default_cache
from app.core.settings import REPO_ROOT
from app.core.timeutil import now_ist
from app.pull import ask as ak
from app.pull import corpus_store
from app.pull.corpus_store import DEFAULT_DIR as DEFAULT_CORPUS_DIR
from app.pull.ingest import IngestSources, NoDocuments
from app.pull.research import SCHEMA, corpus_index, research

STATIC_DIR = REPO_ROOT / "frontend" / "public" / "data" / "research"
RECORD_KEY = f"research:v{SCHEMA}:"
RECENT_SECONDS = 600  # a record that is not worth caching (no documents) is still shown for ten minutes
DEFAULT_CAP = 20


class CapReached(Exception):
    def __init__(self, cap: int):
        super().__init__(f"The daily limit of {cap} fresh research runs has been reached")
        self.cap = cap


class NeedResearch(Exception):
    """Ask was called for a company whose documents have not been read yet."""


@dataclass
class Job:
    symbol: str
    status: str = "running"  # running | failed
    stage: str = "Starting"
    started: float = field(default_factory=time.time)
    reason: str | None = None


class Engine:
    def __init__(
        self,
        *,
        sources_factory: Callable[[], IngestSources] | None = None,
        router_factory: Callable[[], Any] | None = None,
        cache: Cache | None = None,
        static_dir: Path | None = STATIC_DIR,
        corpus_dir: Path | None = DEFAULT_CORPUS_DIR,
        daily_cap: int = DEFAULT_CAP,
        today: Callable[[], date] = lambda: now_ist().date(),
        run_inline: bool = False,
        workers: int = 2,
    ):
        self.cache = cache
        self.corpus_dir = corpus_dir
        self.sources_factory = sources_factory or (lambda: IngestSources(cache=self.cache, corpus_dir=self.corpus_dir))
        self.router_factory = router_factory or (lambda: llm.Router(cache=self.cache) if llm.available("cheap") else None)
        self.static_dir, self.daily_cap, self.today, self.run_inline = static_dir, daily_cap, today, run_inline
        self.jobs: dict[str, Job] = {}
        self._start_lock = threading.Lock()  # FastAPI runs these routes in a thread pool: checking, counting and creating a job must not interleave
        self.recent: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self.pool = None if run_inline else ThreadPoolExecutor(max_workers=workers, thread_name_prefix="research")

    @classmethod
    def from_env(cls) -> "Engine":
        try:
            cap = max(0, int(os.getenv("DAILY_FRESH_RESEARCH_CAP", str(DEFAULT_CAP))))
        except ValueError:
            cap = DEFAULT_CAP
        return cls(cache=default_cache(), daily_cap=cap)

    # ------------------------------------------------------------------ records
    def lookup(self, symbol: str) -> dict[str, Any] | None:
        """A finished record: the one shipped with the app, else one computed earlier, else one shown recently."""
        import json

        if self.static_dir is not None:
            try:
                return json.loads((self.static_dir / f"{symbol}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        stored = self.cache.get(RECORD_KEY + symbol) if self.cache is not None else None
        if isinstance(stored, dict):
            return stored
        held = self.recent.get(symbol)
        if held and time.time() - held[0] < RECENT_SECONDS:
            return held[1]
        return None

    def state(self, symbol: str) -> dict[str, Any]:
        record = self.lookup(symbol)
        if record is not None:
            return {"state": "ready", "record": record}
        job = self.jobs.get(symbol)
        if job is not None and job.status == "running":
            return {"state": "running", "stage": job.stage, "seconds": int(time.time() - job.started)}
        if job is not None and job.status == "failed":
            return {"state": "failed", "reason": job.reason}
        return {"state": "none"}

    # ------------------------------------------------------------------ the cap
    def _cap_key(self) -> str:
        return f"cap:{self.today().isoformat()}"

    def cap_used(self) -> int:
        value = self.cache.get(self._cap_key()) if self.cache is not None else None
        return int(value) if isinstance(value, int) else 0

    def _count_fresh_run(self) -> None:
        if self.cache is not None:
            self.cache.set(self._cap_key(), self.cap_used() + 1)

    # ------------------------------------------------------------------ jobs
    def start(self, symbol: str) -> dict[str, Any]:
        """Begin fresh research unless a record exists or a job is running. Raises CapReached over the daily cap."""
        with self._start_lock:
            current = self.state(symbol)
            if current["state"] in ("ready", "running"):
                return current
            if self.cap_used() >= self.daily_cap:
                raise CapReached(self.daily_cap)
            self._count_fresh_run()
            job = self.jobs[symbol] = Job(symbol)
        if self.pool is None:
            self._run(job)
        else:
            self.pool.submit(self._run, job)
        return self.state(symbol)

    def _run(self, job: Job) -> None:
        try:
            record = research(job.symbol, job.symbol, sources=self.sources_factory(), router=self.router_factory(), progress=lambda message: setattr(job, "stage", message))
        except Exception as exc:  # whatever went wrong, the app gets a reason it can show, never a stack trace
            job.status, job.reason = "failed", f"The research could not be completed ({type(exc).__name__}). Try again in a few minutes."
            return
        if record["status"] in ("ready", "statements_only") and self.cache is not None:
            self.cache.set(RECORD_KEY + job.symbol, record)
        else:
            self.recent[job.symbol] = (time.time(), record)
            while len(self.recent) > 20:
                self.recent.popitem(last=False)
        self.jobs.pop(job.symbol, None)

    # ------------------------------------------------------------------ ask
    def ask(self, symbol: str, question: str) -> dict[str, Any]:
        """Raises ak.BadQuestion, NeedResearch, or NoDocuments (with a reason fit to show)."""
        clean = ak.clean_question(question)
        # The documents are there if a record exists or a saved copy ships with the app (inside backend/, so a deployment that
        # runs from backend/ has it even when the front end's data folder is not on the server).
        shipped = self.corpus_dir is not None and corpus_store.path_for(symbol, self.corpus_dir).exists()
        if self.lookup(symbol) is None and not shipped:
            raise NeedResearch(f"Research {symbol} first: its documents have not been read yet.")
        index, corpus = corpus_index(symbol, self.sources_factory())
        out = ak.ask(clean, index=index, company=corpus.name, router=self.router_factory())
        used = {c["doc"] for c in out["citations"]} | {p["doc"] for p in out["passages"]}
        out["documents"] = [{"id": d.id, "title": d.title, "period": d.period, "url": d.url} for d in corpus.documents if d.id in used]
        return out


__all__ = ["Engine", "CapReached", "NeedResearch", "NoDocuments", "Job"]
