"""Structure checks for evals/sets/missed_threat_v1. No detector is run here: that would break the independence the label rule
depends on. Once the set is frozen (FROZEN.md) a test also fails if a frozen file changes."""

import ast
import hashlib
import json
import re
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "evals" / "sets" / "missed_threat_v1"
BUILDER = ROOT / "evals" / "tools" / "build_missed_threat_set.py"
FROZEN = ("positions.jsonl", "LABEL_RULE.md", "provenance.json")


def rows():
    return [json.loads(line) for line in (SET / "positions.jsonl").read_text().splitlines() if line.strip()]


def test_the_builder_imports_nothing_from_the_detectors():
    tree = ast.parse(BUILDER.read_text())
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in modules if m.startswith("app.detectors")]


def test_the_set_is_well_formed():
    data = rows()
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


def test_real_items_come_from_distinct_puzzles_and_adversarial_items_have_reasons():
    real = [r for r in rows() if r["category"] != "adversarial"]
    assert len({r["puzzle_id"] for r in real}) == len(real)
    for r in rows():
        if r["category"] == "adversarial":
            assert len(r["reason"]) > 20


def test_every_label_has_enough_items_to_report_a_rate():
    labels = [r["label"] for r in rows()]
    assert labels.count("missed") >= 80 and labels.count("met") >= 30 and labels.count("not_applicable") >= 40


def test_constructed_flag_matches_the_category():
    for r in rows():
        assert r["constructed"] == (r["category"].startswith("constructed") or r["category"] == "adversarial")


def test_frozen_files_have_not_changed():
    frozen = SET / "FROZEN.md"
    if not frozen.exists():
        return
    text = frozen.read_text()
    for name in FROZEN:
        digest = hashlib.sha256((SET / name).read_bytes()).hexdigest()
        match = re.search(rf"`{re.escape(name)}` \| `([0-9a-f]{{64}})`", text)
        assert match, f"{name} is not listed in FROZEN.md"
        assert match.group(1) == digest, f"{name} changed after the freeze"
