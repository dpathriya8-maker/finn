"""A scripted stand-in for the model, so the Promise Tracker, Ask and research can be tested without one."""
from app.core.llm import LLMResult, LLMUnavailable


class FakeRouter:
    """`script` maps a purpose ("promises.extract", "promises.judge", "ask") to a dict, or a list of dicts used in turn,
    or a callable(prompt) -> dict, or an exception to raise. Every call is recorded."""

    def __init__(self, script=None, *, model="fake-model"):
        self.script, self.model, self.calls = dict(script or {}), model, []

    def complete_json(self, tier, system, prompt, *, prompt_version, purpose, max_tokens=4096):
        self.calls.append({"tier": tier, "system": system, "prompt": prompt, "purpose": purpose, "version": prompt_version})
        reply = self.script.get(purpose, {})
        if isinstance(reply, list):
            reply = reply.pop(0) if reply else {}
        if callable(reply):
            reply = reply(prompt)
        if isinstance(reply, Exception):
            raise reply
        return LLMResult(reply, self.model, "fake", False, 100, 20, None)

    def purposes(self):
        return [c["purpose"] for c in self.calls]


def unavailable(reason="every model failed"):
    return LLMUnavailable(reason)
