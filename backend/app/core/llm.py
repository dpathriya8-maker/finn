"""LLM router: a cheap tier, a strong tier and a fallback, over Gemini and Groq's REST APIs, with backoff on 429,
a cache so the same input never costs twice, and a log of every call.

NOT VERIFIED AGAINST A LIVE MODEL. No API keys existed when this was written, so the request and response shapes
follow the providers' documented REST formats and are exercised with fakes in tests/test_llm.py. The first real run
(`python -m pipeline.research` with keys in .env) is the real test; anything that fails there fails loudly, as
LLMUnavailable, and the callers turn that into an honest "not run" rather than invented output.

Model names come from the environment only (LLM_CHEAP_MODEL, LLM_STRONG_MODEL, LLM_FALLBACK_MODEL). A name may carry
a provider ("groq:llama-3.3-70b-versatile"); without one, names starting with "gemini" go to Google and the rest to
Groq. Keys are read from GEMINI_API_KEY and GROQ_API_KEY, sent only in headers, and never logged.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.core.cache import Cache, llm_key
from app.core.http import Fetched, FetchError, post_json
from app.core.settings import REPO_ROOT

LOG_PATH = REPO_ROOT / "backend" / ".cache" / "llm_calls.jsonl"
PRICES_PATH = REPO_ROOT / "config" / "llm_prices.json"
RETRY_STATUSES = {429, 500, 502, 503, 504}
BACKOFF_S = (1.0, 4.0)  # so three tries per model; a Retry-After header, up to MAX_WAIT_S, wins
MAX_WAIT_S = 20.0
DAILY_QUOTA_PAUSE_S = 3600.0  # a model whose free DAILY quota is gone is left alone this long before one more try
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMUnavailable(Exception):
    """No model could answer: not configured, out of quota, or every attempt failed. `reason` is safe to show."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ModelSpec:
    provider: str  # "gemini" or "groq"
    name: str

    def __str__(self) -> str:
        return f"{self.provider}:{self.name}"


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    model: str
    provider: str
    cached: bool
    tokens_in: int
    tokens_out: int
    cost_usd: float | None


def parse_model(spec: str) -> ModelSpec:
    spec = spec.strip()
    if ":" in spec:
        provider, _, name = spec.partition(":")
        return ModelSpec(provider.strip().lower(), name.strip())
    return ModelSpec("gemini" if spec.lower().startswith("gemini") else "groq", spec)


def _key_for(provider: str) -> str | None:
    return (os.getenv("GEMINI_API_KEY") if provider == "gemini" else os.getenv("GROQ_API_KEY") if provider == "groq" else None) or None


def chain_for(tier: str) -> list[ModelSpec]:
    """The models to try for a tier, in order, leaving out any whose provider has no key."""
    names = [os.getenv("LLM_STRONG_MODEL") if tier == "strong" else None, os.getenv("LLM_CHEAP_MODEL"), os.getenv("LLM_FALLBACK_MODEL")]
    chain: list[ModelSpec] = []
    for name in names:
        if name and name.strip():
            spec = parse_model(name)
            if spec.provider in ("gemini", "groq") and _key_for(spec.provider) and spec not in chain:
                chain.append(spec)
    return chain


def available(tier: str = "cheap") -> bool:
    """True when a call could be made: a model name and its key are both configured."""
    return bool(chain_for(tier))


def _extract_json(text: str) -> dict[str, Any]:
    """The model's reply as an object. Fences are stripped; a bare list is wrapped as {"items": [...]}."""
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    data = json.loads(cleaned)
    return data if isinstance(data, dict) else {"items": data}


def _request(spec: ModelSpec, system: str, prompt: str, max_tokens: int) -> tuple[str, dict[str, Any], dict[str, str]]:
    """(url, body, headers) for one provider. The key goes in a header, never in the URL, so it cannot end up in a log."""
    key = _key_for(spec.provider) or ""
    if spec.provider == "gemini":
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0, "maxOutputTokens": max_tokens,
                                "thinkingConfig": {"thinkingLevel": "low"}},  # thinking tokens count against the cap; unbounded, they cut the JSON off
        }
        return GEMINI_URL.format(model=spec.name), body, {"x-goog-api-key": key, "Content-Type": "application/json"}
    body = {
        "model": spec.name,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    return GROQ_URL, body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _read(spec: ModelSpec, payload: dict[str, Any]) -> tuple[str, int, int]:
    """(text, tokens in, tokens out) from a provider's reply, or raise ValueError saying what was wrong with it."""
    if spec.provider == "gemini":
        block = (payload.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise ValueError(f"the prompt was blocked ({block})")
        candidates = payload.get("candidates") or []
        if not candidates:
            raise ValueError("no candidates in the reply")
        if candidates[0].get("finishReason") == "MAX_TOKENS":
            raise ValueError("the reply was cut off at the token limit")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        usage = payload.get("usageMetadata") or {}
        return text, int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("no choices in the reply")
    if choices[0].get("finish_reason") == "length":
        raise ValueError("the reply was cut off at the token limit")
    usage = payload.get("usage") or {}
    return (choices[0].get("message") or {}).get("content") or "", int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def _price(spec: ModelSpec, tokens_in: int, tokens_out: int, prices: dict[str, Any]) -> float | None:
    entry = (prices.get("models") or {}).get(spec.name)
    if not entry:
        return None
    return round((tokens_in * entry["input_per_million"] + tokens_out * entry["output_per_million"]) / 1_000_000, 6)


class Router:
    """One per process. `post` and `sleep` are injectable so tests never touch the network or wait."""

    def __init__(
        self,
        *,
        cache: Cache | None = None,
        log_path: Path | None = LOG_PATH,
        post: Callable[..., Fetched] = post_json,
        sleep: Callable[[float], None] = time.sleep,
        prices: dict[str, Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.cache, self.log_path, self.post, self.sleep = cache, log_path, post, sleep
        self.clock = clock
        self._spent: dict[str, float] = {}  # model -> when to try it again, after a "requests per day" 429
        if prices is None:
            try:
                prices = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                prices = {}
        self.prices = prices

    # ------------------------------------------------------------------ logging
    def _log(self, **entry: Any) -> None:
        """One line per call: when, who, how many tokens, what it would cost, whether the cache answered. No prompts, no keys."""
        if self.log_path is None:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}, ensure_ascii=False) + "\n")
        except OSError:
            pass  # a log that cannot be written must never stop a call

    # ------------------------------------------------------------------ the call
    def complete_json(self, tier: str, system: str, prompt: str, *, prompt_version: str, purpose: str, max_tokens: int = 4096) -> LLMResult:
        """The model's JSON answer to `prompt`. Tries each model of the tier in turn, backing off on 429 and 5xx, and
        raises LLMUnavailable if none answers. An answer already cached for the same input, prompt version and model
        is returned without a call."""
        chain = chain_for(tier)
        if not chain:
            raise LLMUnavailable("No model is configured: set GEMINI_API_KEY (or GROQ_API_KEY) and LLM_CHEAP_MODEL in .env.")
        failures: list[str] = []
        for spec in chain:
            key = llm_key(f"{system}\n\n{prompt}", prompt_version, str(spec))
            stored = self.cache.get(f"llm:{key}") if self.cache is not None else None
            if isinstance(stored, dict):
                self._log(provider=spec.provider, model=spec.name, tier=tier, purpose=purpose, tokens_in=0, tokens_out=0, cost_usd=0.0, cached=True, ok=True)
                return LLMResult(stored, spec.name, spec.provider, True, 0, 0, 0.0)
            if self._spent.get(str(spec), 0.0) > self.clock():
                failures.append(f"{spec}: its daily quota is used up")
                continue  # no point waiting through retries for a model that has said it is out for the day
            outcome = self._ask(spec, system, prompt, max_tokens)
            if isinstance(outcome, str):
                failures.append(f"{spec}: {outcome}")
                self._log(provider=spec.provider, model=spec.name, tier=tier, purpose=purpose, ok=False, error=outcome)
                continue
            data, tokens_in, tokens_out = outcome
            cost = _price(spec, tokens_in, tokens_out, self.prices)
            if self.cache is not None:
                self.cache.set(f"llm:{key}", data)
            self._log(provider=spec.provider, model=spec.name, tier=tier, purpose=purpose, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost, cached=False, ok=True)
            return LLMResult(data, spec.name, spec.provider, False, tokens_in, tokens_out, cost)
        raise LLMUnavailable("No model answered: " + "; ".join(failures))

    def _ask(self, spec: ModelSpec, system: str, prompt: str, max_tokens: int) -> tuple[dict[str, Any], int, int] | str:
        """One model, up to three tries. Returns (data, tokens in, tokens out) or a short reason it failed."""
        url, body, headers = _request(spec, system, prompt, max_tokens)
        reason = "no attempt was made"
        for attempt in range(len(BACKOFF_S) + 1):
            try:
                reply = self.post(url, body, headers=headers)
            except FetchError as exc:
                reason = f"the request failed ({exc})"
            else:
                if reply.ok:
                    try:
                        text, tokens_in, tokens_out = _read(spec, reply.json())
                        return _extract_json(text), tokens_in, tokens_out
                    except (ValueError, KeyError, TypeError) as exc:
                        return f"unusable reply ({str(exc)[:120]})"  # a malformed answer will not improve on a retry
                reason = f"HTTP {reply.status}"
                if reply.status == 429 and _is_daily_quota(reply):
                    self._spent[str(spec)] = self.clock() + DAILY_QUOTA_PAUSE_S
                    return f"{reason} (daily quota used up)"
                if reply.status not in RETRY_STATUSES:
                    return reason
                wait = _retry_after(reply)
                if attempt < len(BACKOFF_S):
                    self.sleep(wait if wait is not None else BACKOFF_S[attempt])
                continue
            if attempt < len(BACKOFF_S):
                self.sleep(BACKOFF_S[attempt])
        return reason


def _is_daily_quota(reply: Fetched) -> bool:
    """Gemini says so in the error body ("GenerateRequestsPerDay..."): waiting a few seconds cannot help."""
    return bool(re.search(r"per\s?day", reply.text(), re.I))


def _retry_after(reply: Fetched) -> float | None:
    """How long the provider says to wait: the Retry-After header, else Gemini's own "retryDelay" in the error body."""
    value = next((v for k, v in reply.headers.items() if k.lower() == "retry-after"), None)
    if value is None:
        match = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', reply.text())
        value = match.group(1) if match else None
    try:
        return min(float(value), MAX_WAIT_S) if value is not None else None
    except ValueError:
        return None


def summarise_log(path: Path = LOG_PATH) -> dict[str, Any]:
    """Totals for docs/cost.md: calls, cache hits, tokens, estimated cost, per model."""
    totals: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"calls": 0, "cache_hits": 0, "failures": 0, "models": {}}
    calls = hits = failures = 0
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not row.get("ok"):
            failures += 1
            continue
        calls += 1
        hits += bool(row.get("cached"))
        t = totals.setdefault(f"{row['provider']}:{row['model']}", {"calls": 0, "cache_hits": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "priced": False})
        t["calls"] += 1
        t["cache_hits"] += bool(row.get("cached"))
        t["tokens_in"] += row.get("tokens_in") or 0
        t["tokens_out"] += row.get("tokens_out") or 0
        if row.get("cost_usd") is not None and not row.get("cached"):
            t["cost_usd"] = round(t["cost_usd"] + row["cost_usd"], 6)
            t["priced"] = True
    return {"calls": calls, "cache_hits": hits, "failures": failures, "models": totals}


def report(path: Path = LOG_PATH) -> str:
    """The usage log as a Markdown table, for docs/cost.md: `python -m app.core.llm`."""
    summary = summarise_log(path)
    if summary["calls"] == 0 and summary["failures"] == 0:
        return "No model calls have been logged yet.\n"
    lines = [
        f"{summary['calls']} calls ({summary['cache_hits']} answered from the cache, {summary['failures']} failed).",
        "",
        "| Model | Calls | From cache | Tokens in | Tokens out | Est. list-price cost |",
        "|---|---|---|---|---|---|",
    ]
    for name, m in sorted(summary["models"].items()):
        cost = f"${m['cost_usd']:.4f}" if m["priced"] else "free tier / no price set"
        lines.append(f"| {name} | {m['calls']} | {m['cache_hits']} | {m['tokens_in']:,} | {m['tokens_out']:,} | {cost} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(report())
