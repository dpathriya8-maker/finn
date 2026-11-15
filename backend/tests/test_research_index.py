"""The research index must list every configured research company, whichever symbols a run was for."""
import json

from pipeline import research as pr


def record(symbol):
    return {"symbol": symbol, "name": symbol.title(), "status": "ready", "documents": [1, 2], "generated_at": "2026-11-15T21:00:00+05:30"}


def test_a_run_for_one_symbol_does_not_shrink_the_index(tmp_path, monkeypatch):
    configured = [{"symbol": "AAA", "name": "A"}, {"symbol": "BBB", "name": "B"}, {"symbol": "CCC", "name": "C"}]
    monkeypatch.setattr(pr, "load_companies", lambda: configured)
    for sym in ("AAA", "BBB", "CCC", "XYZ"):
        (tmp_path / f"{sym}.json").write_text(json.dumps(record(sym)), encoding="utf-8")
    pr.write_index([{"symbol": "BBB", "name": "B"}], tmp_path)  # a run for BBB only
    listed = [c["symbol"] for c in json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["companies"]]
    assert listed == ["AAA", "BBB", "CCC"]
    pr.write_index([{"symbol": "XYZ", "name": "X"}], tmp_path)  # a symbol outside the config that was just researched is listed too
    listed = [c["symbol"] for c in json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["companies"]]
    assert listed == ["AAA", "BBB", "CCC", "XYZ"]


def test_a_configured_company_with_no_record_is_left_out(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "load_companies", lambda: [{"symbol": "AAA", "name": "A"}, {"symbol": "BBB", "name": "B"}])
    (tmp_path / "AAA.json").write_text(json.dumps(record("AAA")), encoding="utf-8")
    pr.write_index([], tmp_path)
    assert [c["symbol"] for c in json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["companies"]] == ["AAA"]
