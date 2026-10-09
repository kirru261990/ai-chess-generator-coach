import importlib.util
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[2] / "evals" / "tools" / "run_e2.py"


def runner():
    spec = importlib.util.spec_from_file_location("run_e2", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def result(text_ok=True, scored=True, claims=()):
    texts = {c: "some text" if text_ok else "" for c in ("raw", "grounded", "verified")}
    return {"id": "x", "kind": "good", "texts": texts, "unverifiable": {c: [] for c in texts},
            "claims": {c: [{"correct": ok} for ok in claims] for c in texts},
            "scored": dict.fromkeys(texts, scored), "notes": {"verified_status": "verified"}}


def test_a_text_whose_extraction_failed_is_counted_as_not_scored_not_as_correct():
    m = runner()
    s = m.summarise([result(), result(scored=False)])
    assert s["raw"]["texts_not_scored_extraction_failed"] == 1 and s["raw"]["texts"] == 2


def test_empty_texts_are_not_confused_with_failed_extractions():
    m = runner()
    s = m.summarise([result(text_ok=False, scored=False)])
    assert s["raw"]["empty_texts"] == 1 and s["raw"]["texts_not_scored_extraction_failed"] == 0


def test_the_report_states_scoring_coverage(tmp_path):
    import json
    import subprocess
    import sys

    m = runner()
    summary = m.summarise([result(scored=False)])
    run_dir = tmp_path / "e2_19990101_000000"
    run_dir.mkdir()
    (run_dir / "results.json").write_text(json.dumps({
        "meta": {"set": "evals/sets/e2_v1", "items": 1, "model": "m", "prompts": {}, "verifier": "1", "score_budget": {"depth": 18},
                 "usd": 0, "tokens": {"input": 0, "output": 0}},
        "summary": summary, "results": [result(scored=False)]}))
    report = RUNNER.with_name("report_e2.py")
    out = subprocess.run([sys.executable, str(report), str(run_dir / "results.json")], capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    written = Path(out.stdout.strip())
    try:
        text = written.read_text()
        assert "could not be scored" in text and "NOT counted as correct" in text
    finally:
        written.unlink()  # this was a test report; never leave it in evals/reports


def test_an_interrupted_run_keeps_its_finished_items_and_can_resume(tmp_path, monkeypatch):
    import json

    from app import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")  # never read the real usage ledger

    m = runner()
    m.ROOT = tmp_path  # keep all output in the temp folder
    set_dir = tmp_path / "evals" / "sets" / "e2_v9"
    set_dir.mkdir(parents=True)
    items = [{"id": f"e2-00{i}", "kind": "good", "fen": "x", "user_color": "white", "move_uci": "e2e4", "move_san": "e4"}
             for i in (1, 2, 3)]
    (set_dir / "positions.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
    calls = []

    def fake_run_item(engine, drafter, item, tally):
        calls.append(item["id"])
        if item["id"] == "e2-003" and len(calls) == 3:  # the model runs out of credit on the third item
            raise m.CoachUnavailable("credit balance is too low")
        tally.tokens["input"] += 10
        return {**result(), "id": item["id"]}

    class FakeEngine:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(m, "run_item", fake_run_item)
    monkeypatch.setattr(m, "Engine", FakeEngine)
    monkeypatch.setattr(m, "AnthropicDrafter", lambda **k: type("D", (), {"model": "fake"})())
    import pytest

    with pytest.raises(SystemExit) as stop:
        m.main(["run", "e2_v9"])
    assert "--resume" in str(stop.value)
    out = next((tmp_path / "evals" / "runs").iterdir())
    saved = [json.loads(line)["id"] for line in (out / "items.jsonl").read_text().splitlines()]
    assert saved == ["e2-001", "e2-002"]  # nothing lost
    m.main(["run", "e2_v9", "--resume", str(out)])
    assert calls == ["e2-001", "e2-002", "e2-003", "e2-003"]  # only the missing item was redone
    final = json.loads((out / "results.json").read_text())
    assert [r["id"] for r in final["results"]] == ["e2-001", "e2-002", "e2-003"]
    assert final["meta"]["tokens"]["input"] == 30  # cost of the first part is kept


def test_a_run_refuses_to_start_when_the_month_budget_cannot_cover_it(tmp_path, monkeypatch):
    import json

    import pytest

    from app import config
    from app.coach import usage

    m = runner()
    m.ROOT = tmp_path
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "0.05")  # a 3-item run needs about 0.12
    set_dir = tmp_path / "evals" / "sets" / "e2_v9"
    set_dir.mkdir(parents=True)
    items = [{"id": f"e2-00{i}", "kind": "good", "fen": "x", "user_color": "white", "move_uci": "e2e4", "move_san": "e4"}
             for i in (1, 2, 3)]
    (set_dir / "positions.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
    called = []
    monkeypatch.setattr(m, "run_item", lambda *a: called.append(1))
    monkeypatch.setattr(m, "AnthropicDrafter", lambda **k: type("D", (), {"model": "fake"})())
    with pytest.raises(SystemExit) as stop:
        m.main(["run", "e2_v9"])
    assert "before spending anything" in str(stop.value) and called == []
    assert usage.summary()["spent_usd"] == 0
