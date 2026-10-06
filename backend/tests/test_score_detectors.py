import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "evals" / "tools" / "score_detectors.py"
REPORT = max((ROOT / "evals" / "reports").glob("real_play_v1_*.json"))


def mod():
    spec = importlib.util.spec_from_file_location("score_detectors", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_wilson_interval_matches_known_values():
    w = mod().wilson
    assert w(0, 0) is None
    lo, hi = w(43, 43)
    assert lo == pytest.approx(0.918, abs=0.002) and hi == 1.0
    lo, hi = w(9, 10)
    assert (lo, hi) == pytest.approx((0.596, 0.982), abs=0.002)


def test_frac_formats_denominators_and_empty_cases():
    f = mod().frac
    assert f(0, 0) == "n/a (0 cases)"
    assert f(42, 44).startswith("42/44 = 0.95 (95% CI 0.85-0.99)")


def test_metrics_count_precision_and_recall_for_the_missed_class():
    items = [
        {"label": "missed", "static": "missed", "evidence": "missed"},
        {"label": "missed", "static": "missed", "evidence": "uncertain"},
        {"label": "uncertain", "static": "missed", "evidence": "uncertain"},
        {"label": "taken", "static": "taken", "evidence": "taken"},
    ]
    s = mod().metrics(items, "static")
    assert s["precision"] == [2, 3] and s["recall"] == [2, 2]
    e = mod().metrics(items, "evidence")
    assert e["precision"] == [1, 1] and e["recall"] == [1, 2] and e["exact_agreement"] == [3, 4]


def test_the_committed_report_matches_the_frozen_set_and_can_be_recomputed_from_its_items():
    data = json.loads(REPORT.read_text())
    positions = ROOT / "evals" / "sets" / "real_play_v1" / "positions.jsonl"
    assert data["meta"]["positions_sha256"] == hashlib.sha256(positions.read_bytes()).hexdigest()
    assert len(data["items"]) == 202 and all({"static", "evidence"} <= set(i) for i in data["items"])
    m = mod()
    assert m.build(data["items"]) == data["report"]  # every table is derived from the stored per-item results
    assert data["meta"]["depth"] == 10 and data["meta"]["engine"].startswith("Stockfish")


def test_the_report_records_the_detector_versions_that_were_scored():
    data = json.loads(REPORT.read_text())
    from app.detectors import hanging_own, missed_free

    assert data["meta"]["detector_versions"] == {"hanging_own": hanging_own.VERSION, "missed_free": missed_free.VERSION}
    notes = REPORT.with_name(REPORT.stem + "_notes.md").read_text().lower()
    for caveat in ("not how often", "partly reflects a shared definition", "no real", "unmeasured"):
        assert caveat in notes
