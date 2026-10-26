"""Structure checks for the M3 eval sets evals/sets/missed_threat_v1 and _v2. No detector is run here: that would break the
independence the label rule depends on. Once a set is frozen (FROZEN.md) a test also fails if a frozen file changes."""

import ast
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import chess
import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "evals" / "tools"
MIN_ITEMS = {"missed_threat_v1": (80, 30, 40), "missed_threat_v2": (80, 25, 40)}  # missed, met, not_applicable
BUILDERS = [TOOLS / "build_missed_threat_set.py", TOOLS / "build_missed_threat_set_v2.py"]
FROZEN = ("positions.jsonl", "LABEL_RULE.md", "provenance.json")
SETS = list(MIN_ITEMS)


def rows(name):
    return [json.loads(line) for line in (ROOT / "evals" / "sets" / name / "positions.jsonl").read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("builder", BUILDERS)
def test_the_builders_import_nothing_from_the_detectors(builder):
    tree = ast.parse(builder.read_text())
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in modules if m.startswith("app.detectors")]


@pytest.mark.parametrize("name", SETS)
def test_the_set_is_well_formed(name):
    data = rows(name)
    assert len({r["id"] for r in data}) == len(data)
    assert len({(r["fen"], r["move_uci"]) for r in data}) == len(data)
    for r in data:
        board = chess.Board(r["fen"])
        assert board.is_valid()
        move = chess.Move.from_uci(r["move_uci"])
        assert move in board.legal_moves and board.san(move) == r["move_san"]
        assert r["label"] in {"missed", "met", "uncertain", "not_applicable"}
        assert r["ply"] == 2 * (board.fullmove_number - 1) + (0 if board.turn else 1) and r["ply"] >= 4
        assert not board.is_check()
        if r.get("previous_fen"):
            assert chess.Board(r["previous_fen"]).is_valid()


@pytest.mark.parametrize("name", SETS)
def test_real_items_come_from_distinct_puzzles_and_adversarial_items_have_reasons(name):
    real = [r for r in rows(name) if r["category"] != "adversarial"]
    assert len({r["puzzle_id"] for r in real}) == len(real)
    for r in rows(name):
        if r["category"] == "adversarial":
            assert len(r["reason"]) > 20


@pytest.mark.parametrize("name", SETS)
def test_every_label_has_enough_items_to_report_a_rate(name):
    labels = [r["label"] for r in rows(name)]
    missed, met, na = MIN_ITEMS[name]
    assert labels.count("missed") >= missed and labels.count("met") >= met and labels.count("not_applicable") >= na


@pytest.mark.parametrize("name", SETS)
def test_constructed_flag_matches_the_category(name):
    for r in rows(name):
        assert r["constructed"] == (r["category"].startswith("constructed") or r["category"] == "adversarial")


def test_v2_uses_no_puzzle_from_v1():
    v1 = {r["puzzle_id"] for r in rows("missed_threat_v1") if r["category"] != "adversarial"}
    v2 = {r["puzzle_id"] for r in rows("missed_threat_v2") if r["category"] != "adversarial"}
    assert not v1 & v2


def test_v2_met_items_have_a_concrete_threat():
    for r in rows("missed_threat_v2"):
        if r["category"] == "met_real":
            assert r["threat_basis"] in {"static", "engine_line"}


@pytest.mark.parametrize("name", SETS)
def test_frozen_files_have_not_changed(name):
    folder = ROOT / "evals" / "sets" / name
    frozen = folder / "FROZEN.md"
    if not frozen.exists():
        return
    text = frozen.read_text()
    for file in FROZEN:
        digest = hashlib.sha256((folder / file).read_bytes()).hexdigest()
        match = re.search(rf"`{re.escape(file)}` \| `([0-9a-f]{{64}})`", text)
        assert match, f"{file} is not listed in FROZEN.md"
        assert match.group(1) == digest, f"{file} changed after the freeze"


def test_the_scorer_splits_real_and_constructed_items_without_overlap():
    spec = importlib.util.spec_from_file_location("score_missed_threat", TOOLS / "score_missed_threat.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    real, constructed = [p for name, p in scorer.GROUPS.items() if name.startswith(("real", "constructed"))]
    for name in SETS:
        data = rows(name)
        assert not [r for r in data if real(r) and constructed(r)]
        assert all(real(r) or constructed(r) for r in data)
