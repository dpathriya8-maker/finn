"""The SQLite cache. It saves work, so it must never become a way for a run to fail."""
import sqlite3

from app.core.cache import Cache, digest_key, llm_key


def test_values_round_trip_and_can_be_replaced_and_removed():
    cache = Cache(":memory:")
    assert cache.get("k") is None and len(cache) == 0
    assert cache.set("k", {"a": [1, 2, {"b": None}], "text": "₹ crore"})
    assert cache.get("k") == {"a": [1, 2, {"b": None}], "text": "₹ crore"}
    cache.set("k", 7)
    assert cache.get("k") == 7 and len(cache) == 1
    cache.delete("k")
    assert cache.get("k") is None and len(cache) == 0


def test_what_was_stored_is_still_there_after_a_restart(tmp_path):
    path = tmp_path / "nested" / "finn.sqlite"  # the folder is created on demand
    first = Cache(path)
    first.set("k", [1, 2, 3])
    first.close()
    second = Cache(path)
    assert second.get("k") == [1, 2, 3]
    second.close()


def test_a_cache_that_cannot_be_opened_behaves_as_an_empty_one(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    cache = Cache(blocker / "inside" / "finn.sqlite")  # the parent is a file, so nothing can be created there
    assert not cache.usable
    assert cache.get("k") is None and cache.set("k", 1) is False and len(cache) == 0
    cache.delete("k")
    cache.close()  # none of this raises


def test_a_damaged_value_is_a_miss_not_a_crash(tmp_path):
    path = tmp_path / "c.sqlite"
    cache = Cache(path)
    cache.set("k", 1)
    other = sqlite3.connect(path)
    other.execute("UPDATE kv SET value = '{not json'")
    other.commit()
    other.close()
    assert cache.get("k") is None
    cache.close()


def test_a_value_that_is_not_json_is_refused_quietly():
    cache = Cache(":memory:")
    assert cache.set("k", {1, 2}) is False  # a set is not JSON
    assert cache.get("k") is None


def test_digest_keys_cannot_be_forged_by_moving_a_boundary():
    assert digest_key("ab", "c") != digest_key("a", "bc")
    assert digest_key(b"x") == digest_key("x")
    assert len(digest_key("a")) == 64 and digest_key("a") == digest_key("a")


def test_the_model_key_changes_with_the_document_the_prompt_and_the_model():
    base = llm_key(b"pdf bytes", "promises-v1", "model-a")
    assert base == llm_key(b"pdf bytes", "promises-v1", "model-a")  # the same input never costs twice
    others = {llm_key(b"other bytes", "promises-v1", "model-a"), llm_key(b"pdf bytes", "promises-v2", "model-a"), llm_key(b"pdf bytes", "promises-v1", "model-b")}
    assert len(others | {base}) == 4
