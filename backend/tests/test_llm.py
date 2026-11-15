"""The LLM router, with a fake transport: request shapes, backoff, fallback, cache, log, and that keys never leak.
Nothing here calls a real model; see the module's own note."""
import json

import pytest

from app.core import llm
from app.core.cache import Cache
from app.core.http import BlockedUrl, Fetched, FetchError, post_json

SENTINEL = "this-text-must-never-appear-in-a-url-or-log"  # stands in for a key; not a real one


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", SENTINEL)
    monkeypatch.setenv("GROQ_API_KEY", SENTINEL + "-groq")
    monkeypatch.setenv("LLM_CHEAP_MODEL", "gemini-flash-lite-test")
    monkeypatch.setenv("LLM_STRONG_MODEL", "gemini-flash-test")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "groq:llama-test")


def gemini_reply(text='{"ok": true}', tin=120, tout=30, **extra):
    body = {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": tin, "candidatesTokenCount": tout}}
    return Fetched("u", 200, json.dumps({**body, **extra}).encode())


def groq_reply(text='{"ok": true}', tin=100, tout=20, finish="stop"):
    body = {"choices": [{"message": {"content": text}, "finish_reason": finish}], "usage": {"prompt_tokens": tin, "completion_tokens": tout}}
    return Fetched("u", 200, json.dumps(body).encode())


def status(code, **headers):
    return Fetched("u", code, b'{"error": "x"}', headers)


class Transport:
    """Plays back a list of replies, one per call, and remembers what was sent."""

    def __init__(self, *replies):
        self.replies, self.sent = list(replies), []

    def __call__(self, url, payload, *, headers=None, **_):
        self.sent.append((url, payload, headers))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def router(transport, tmp_path, cache=None, sleeps=None):
    return llm.Router(cache=cache, log_path=tmp_path / "calls.jsonl", post=transport, sleep=(sleeps.append if sleeps is not None else lambda _s: None), prices={})


def ask(r, tier="cheap", prompt="p", **kw):
    return r.complete_json(tier, "Reply with a JSON object.", prompt, prompt_version="t1", purpose="test", **kw)


# ---------------------------------------------------------------------------------------------- models
@pytest.mark.parametrize(
    "spec, provider, name",
    [("gemini-2.5-flash", "gemini", "gemini-2.5-flash"), ("llama-3.3-70b", "groq", "llama-3.3-70b"), ("groq:gemma", "groq", "gemma"), ("  Gemini:x  ", "gemini", "x")],
)
def test_a_model_name_may_name_its_provider_and_otherwise_it_is_guessed_from_the_name(spec, provider, name):
    assert (llm.parse_model(spec).provider, llm.parse_model(spec).name) == (provider, name)


def test_the_strong_tier_tries_its_own_model_first_then_the_cheap_one_then_the_fallback(monkeypatch):
    assert [m.name for m in llm.chain_for("strong")] == ["gemini-flash-test", "gemini-flash-lite-test", "llama-test"]
    assert [m.name for m in llm.chain_for("cheap")] == ["gemini-flash-lite-test", "llama-test"]


def test_a_model_whose_provider_has_no_key_is_left_out(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    assert [m.name for m in llm.chain_for("cheap")] == ["gemini-flash-lite-test"]
    monkeypatch.delenv("GEMINI_API_KEY")
    assert llm.chain_for("cheap") == [] and not llm.available()


def test_nothing_is_configured_so_nothing_is_called(monkeypatch, tmp_path):
    for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "LLM_CHEAP_MODEL"):
        monkeypatch.delenv(name)
    transport = Transport()
    with pytest.raises(llm.LLMUnavailable, match="No model is configured"):
        ask(router(transport, tmp_path))
    assert transport.sent == []


# ---------------------------------------------------------------------------------------------- requests
def test_gemini_gets_the_documented_request_with_the_key_in_a_header_and_never_in_the_url(tmp_path):
    t = Transport(gemini_reply())
    result = ask(router(t, tmp_path), max_tokens=777)
    url, body, headers = t.sent[0]
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-test:generateContent"
    assert SENTINEL not in url and headers["x-goog-api-key"] == SENTINEL
    assert body["generationConfig"] == {"responseMimeType": "application/json", "temperature": 0, "maxOutputTokens": 777, "thinkingConfig": {"thinkingLevel": "low"}}
    assert body["systemInstruction"]["parts"][0]["text"] == "Reply with a JSON object." and body["contents"][0]["parts"][0]["text"] == "p"
    assert (result.data, result.provider, result.model, result.tokens_in, result.tokens_out, result.cached) == ({"ok": True}, "gemini", "gemini-flash-lite-test", 120, 30, False)


def test_groq_gets_the_openai_style_request_with_json_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_CHEAP_MODEL", "groq:llama-test")
    t = Transport(groq_reply())
    result = ask(router(t, tmp_path))
    url, body, headers = t.sent[0]
    assert url == "https://api.groq.com/openai/v1/chat/completions" and headers["Authorization"] == f"Bearer {SENTINEL}-groq"
    assert body["model"] == "llama-test" and body["response_format"] == {"type": "json_object"} and body["temperature"] == 0
    assert body["messages"][0]["role"] == "system" and (result.provider, result.tokens_in, result.tokens_out) == ("groq", 100, 20)


@pytest.mark.parametrize("text, expected", [('```json\n{"a": 1}\n```', {"a": 1}), ('[{"q": 1}, {"q": 2}]', {"items": [{"q": 1}, {"q": 2}]}), ('  {"a": [1, 2]}  ', {"a": [1, 2]})])
def test_replies_in_fences_or_as_a_bare_list_are_normalised_to_an_object(text, expected, tmp_path):
    assert ask(router(Transport(gemini_reply(text)), tmp_path)).data == expected


# ---------------------------------------------------------------------------------------------- failures
def test_a_429_waits_as_long_as_the_provider_says_then_tries_again(tmp_path):
    sleeps = []
    result = ask(router(Transport(status(429, **{"Retry-After": "7"}), gemini_reply()), tmp_path, sleeps=sleeps))
    assert result.data == {"ok": True} and sleeps == [7.0]


def test_a_missing_retry_after_uses_the_backoff_and_a_huge_one_is_capped(tmp_path):
    sleeps = []
    ask(router(Transport(status(503), status(429, **{"Retry-After": "9999"}), gemini_reply()), tmp_path, sleeps=sleeps))
    assert sleeps == [llm.BACKOFF_S[0], llm.MAX_WAIT_S]


def test_when_the_first_model_keeps_failing_the_fallback_provider_answers(tmp_path):
    t = Transport(status(429), status(429), status(429), groq_reply('{"from": "fallback"}'))
    result = ask(router(t, tmp_path))
    assert result.data == {"from": "fallback"} and result.provider == "groq"
    assert [u.split("/")[2] for u, _b, _h in t.sent] == ["generativelanguage.googleapis.com"] * 3 + ["api.groq.com"]  # three tries, then the fallback


def test_an_error_that_retrying_cannot_fix_moves_on_at_once(tmp_path):
    t = Transport(status(400), groq_reply())
    result = ask(router(t, tmp_path))
    assert len(t.sent) == 2 and result.provider == "groq"  # no three tries for a 400


def test_when_every_model_fails_the_reason_is_reported_and_no_key_is_in_it(tmp_path):
    t = Transport(status(429), status(429), status(429), status(500), status(500), status(500))
    with pytest.raises(llm.LLMUnavailable) as caught:
        ask(router(t, tmp_path))
    assert "gemini:gemini-flash-lite-test: HTTP 429" in caught.value.reason and "groq:llama-test: HTTP 500" in caught.value.reason
    assert SENTINEL not in caught.value.reason and SENTINEL not in str(caught.value)


@pytest.mark.parametrize(
    "bad, why",
    [
        (gemini_reply("not json at all"), "unusable reply"),
        (Fetched("u", 200, json.dumps({"candidates": []}).encode()), "no candidates"),
        (Fetched("u", 200, json.dumps({"candidates": [{"content": {"parts": [{"text": "{"}]}, "finishReason": "MAX_TOKENS"}]}).encode()), "token limit"),
        (Fetched("u", 200, json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}).encode()), "was blocked"),
        (Fetched("u", 200, b"<html>gateway</html>"), "unusable reply"),
    ],
)
def test_a_reply_that_cannot_be_used_is_not_retried_and_the_next_model_gets_a_turn(bad, why, tmp_path):
    t = Transport(bad, groq_reply())
    assert ask(router(t, tmp_path)).provider == "groq" and len(t.sent) == 2
    t2 = Transport(bad, bad)
    with pytest.raises(llm.LLMUnavailable, match=why):
        ask(router(t2, tmp_path))


def test_a_network_error_is_retried_and_its_message_is_not_passed_on(tmp_path):
    sleeps = []
    t = Transport(FetchError("ConnectionError"), gemini_reply())
    assert ask(router(t, tmp_path, sleeps=sleeps)).data == {"ok": True} and sleeps == [llm.BACKOFF_S[0]]


# ---------------------------------------------------------------------------------------------- the cache and the log
def test_the_same_input_never_costs_twice(tmp_path):
    cache, t = Cache(":memory:"), Transport(gemini_reply('{"n": 1}'))
    r = router(t, tmp_path, cache=cache)
    first, second = ask(r, prompt="same input"), ask(r, prompt="same input")
    assert first.data == second.data == {"n": 1} and (first.cached, second.cached) == (False, True) and len(t.sent) == 1
    assert (second.tokens_in, second.tokens_out) == (0, 0)


def test_a_different_prompt_version_or_input_or_model_is_a_new_call(tmp_path, monkeypatch):
    cache, t = Cache(":memory:"), Transport(*[gemini_reply('{"n": %d}' % i) for i in range(4)])
    r = router(t, tmp_path, cache=cache)
    ask(r, prompt="a")
    ask(r, prompt="b")
    r.complete_json("cheap", "Reply with a JSON object.", "a", prompt_version="t2", purpose="test")
    monkeypatch.setenv("LLM_CHEAP_MODEL", "gemini-other")
    ask(r, prompt="a")
    assert len(t.sent) == 4


def test_every_call_is_logged_with_tokens_and_cache_status_but_never_the_prompt_or_the_key(tmp_path):
    cache, log = Cache(":memory:"), tmp_path / "calls.jsonl"
    r = llm.Router(cache=cache, log_path=log, post=Transport(gemini_reply(tin=500, tout=60)), sleep=lambda _s: None, prices={"models": {"gemini-flash-lite-test": {"input_per_million": 0.10, "output_per_million": 0.40}}})
    ask(r, prompt="a very private prompt about a company")
    ask(r, prompt="a very private prompt about a company")
    raw = log.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [(x["cached"], x["tokens_in"], x["tokens_out"]) for x in rows] == [(False, 500, 60), (True, 0, 0)]
    assert rows[0]["cost_usd"] == pytest.approx(0.000074) and rows[0]["purpose"] == "test" and rows[0]["provider"] == "gemini"
    assert "private prompt" not in raw and SENTINEL not in raw
    summary = llm.summarise_log(log)
    assert summary["calls"] == 2 and summary["cache_hits"] == 1
    assert summary["models"]["gemini:gemini-flash-lite-test"]["tokens_in"] == 500


def test_failures_are_logged_too_and_a_log_that_cannot_be_written_never_stops_a_call(tmp_path):
    r = llm.Router(cache=None, log_path=tmp_path / "nope" / "x" / "calls.jsonl", post=Transport(gemini_reply()), sleep=lambda _s: None, prices={})
    (tmp_path / "nope").write_text("a file where the log folder should be")
    assert ask(r).data == {"ok": True}
    t = Transport(status(400), status(400))
    r2 = router(t, tmp_path)
    with pytest.raises(llm.LLMUnavailable):
        ask(r2)
    assert llm.summarise_log(tmp_path / "calls.jsonl")["failures"] == 2


def test_with_no_price_configured_the_cost_is_unknown_not_zero(tmp_path):
    assert ask(router(Transport(gemini_reply()), tmp_path)).cost_usd is None


# ---------------------------------------------------------------------------------------------- the safe POST
@pytest.mark.parametrize(
    "url",
    ["https://evil.example.com/v1", "http://api.groq.com/openai/v1/chat/completions", "https://api.groq.com.evil.example/x", "https://sub.api.groq.com/x", "https://user:pw@api.groq.com/x", "https://api.groq.com:8443/x"],
)
def test_the_post_goes_only_to_the_fixed_provider_hosts(url):
    with pytest.raises(BlockedUrl):
        post_json(url, {"a": 1}, headers={"Authorization": "Bearer x"})


def test_the_usage_report_is_a_table_a_reader_can_paste_into_the_cost_doc(tmp_path):
    log = tmp_path / "calls.jsonl"
    assert llm.report(log) == "No model calls have been logged yet.\n"
    r = llm.Router(cache=Cache(":memory:"), log_path=log, post=Transport(gemini_reply(tin=500, tout=60)), sleep=lambda _s: None, prices={})
    ask(r, prompt="x")
    ask(r, prompt="x")
    text = llm.report(log)
    assert "2 calls (1 answered from the cache, 0 failed)" in text and "| gemini:gemini-flash-lite-test | 2 | 1 | 500 | 60 | free tier / no price set |" in text
