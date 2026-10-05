"""Structure checks for evals/sets/real_play_v1. No detector is run here: that would break the
independence the label rule depends on."""

import ast
import json
from pathlib import Path

import chess

SET = Path(__file__).resolve().parents[2] / "evals" / "sets" / "real_play_v1"
BUILDER = Path(__file__).resolve().parents[2] / "evals" / "tools" / "build_real_play_set.py"


def rows():
    return [json.loads(line) for line in (SET / "positions.jsonl").read_text().splitlines() if line.strip()]


def test_the_builder_imports_nothing_from_the_detectors():
    tree = ast.parse(BUILDER.read_text())
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in modules if m.startswith("app.detectors")]


def test_the_set_is_well_formed_and_matches_the_rule_counts():
    data = rows()
    assert len({r["id"] for r in data}) == len(data) == 202
    assert len({(r["fen"], r["move_uci"], r["detector"]) for r in data}) == len(data)
    for r in data:
        board = chess.Board(r["fen"])
        assert board.is_valid()
        move = chess.Move.from_uci(r["move_uci"])
        assert move in board.legal_moves and board.san(move) == r["move_san"]
        assert r["detector"] in {"missed_free", "hanging_own"}
        assert r["label"] in {"taken", "missed", "not_applicable", "uncertain"}
    cats = {}
    for r in data:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    assert cats == {"real_taken": 40, "real_blunder": 40, "real_safe": 40, "constructed_miss": 40,
                    "engine_no_opportunity": 20, "adversarial": 22}


def test_real_items_come_from_distinct_puzzles_in_even_rating_bands():
    real = [r for r in rows() if r["category"] != "adversarial"]
    assert len({r["puzzle_id"] for r in real}) == len(real)  # no puzzle supports two items
    assert {b: sum(r["band"] == b for r in real) for b in (400, 600, 800, 1000)} == {400: 45, 600: 45, 800: 45, 1000: 45}


def test_every_adversarial_item_has_a_written_reason_and_constructed_items_are_marked():
    for r in rows():
        if r["category"] == "adversarial":
            assert len(r["reason"]) > 20
        assert r["constructed"] == r["category"].startswith(("constructed", "adversarial"))


def test_ids_do_not_reveal_the_category():
    by = {}
    for r in rows():
        by.setdefault(r["category"], []).append(int(r["id"].split("-")[1]))
    means = [sum(v) / len(v) for v in by.values()]
    assert max(means) - min(means) < 60  # contiguous blocks per category would be a leak


def test_provenance_says_no_detector_has_run_and_the_set_is_not_frozen():
    prov = json.loads((SET / "provenance.json").read_text())
    assert prov["detectors_run"] is False and prov["frozen"] is False
    assert prov["engine"].startswith("Stockfish") and prov["oracle_depth"] == 14 and prov["miss_loss_cp"] == 300
    assert len(prov["puzzle_file_sha256"]) == 64 and prov["shortfall"] == {}


def test_the_hand_check_sheets_do_not_show_labels():
    for name in ("handcheck_owner.md", "handcheck_second.md"):
        text = (SET / name).read_text().lower()
        for leak in ("not_applicable", "constructed", "adversarial", "real_taken", "label:", "reason"):
            assert leak not in text
