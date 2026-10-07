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
        "meta": {"items": 1, "model": "m", "prompts": {}, "verifier": "1", "score_budget": {"depth": 18},
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
