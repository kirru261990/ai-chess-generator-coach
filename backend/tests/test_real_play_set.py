"""Structure checks for evals/sets/real_play_v1. No detector is run here: that would break the
independence the label rule depends on."""

import ast
import importlib.util
import json
from pathlib import Path

import chess

SET = Path(__file__).resolve().parents[2] / "evals" / "sets" / "real_play_v1"
BUILDER = Path(__file__).resolve().parents[2] / "evals" / "tools" / "build_real_play_set.py"


def builder():
    spec = importlib.util.spec_from_file_location("build_real_play_set", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
                    "no_opportunity": 20, "adversarial": 22}


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


def test_no_item_carries_an_excluded_theme():
    excluded = builder().EXCLUDED_THEMES
    bad = [(r["id"], r["themes"]) for r in rows() if excluded & set(r["themes"])]
    assert bad == []  # the negatives sampler once skipped this filter (review of PR #21)


def test_every_stored_item_agrees_with_the_independent_material_check():
    b = builder()
    for r in rows():
        board = chess.Board(r["fen"])
        move = chess.Move.from_uci(r["move_uci"])
        where = (r["id"], r["category"], r["label"], r["fen"], r["move_uci"])
        if r["category"] == "no_opportunity":
            # a capture that legally wins material means "no opportunity" is wrong, however
            # much the engine may prefer another move (found in review: rp1-028)
            assert b.best_capture_net(board) < b.MIN_GAIN, where
        elif r["category"] == "real_taken":
            assert b.capture_net(board, move) >= b.MIN_GAIN, where
        elif r["category"] == "constructed_miss":
            assert b.best_capture_net(board) >= b.MIN_GAIN and not board.is_capture(move), where
        elif r["category"] == "real_blunder":
            assert b.hang_gain_after(board, move) >= b.MIN_GAIN, where
        elif r["category"] == "real_safe":
            assert b.hang_gain_after(board, move) < b.MIN_GAIN, where
        elif r["category"] == "adversarial":
            b._check_adversarial_label(r["detector"], r["label"], board, move, r["fen"], r["move_uci"])


def test_the_sheets_ask_questions_that_distinguish_every_label():
    for name in ("handcheck_owner.md", "handcheck_second.md"):
        text = (SET / name).read_text()
        items = text.count("\n## ")
        assert items >= 30
        assert text.count("  - A. ") == items and text.count("  - B. ") == items and text.count("  - C. ") == items
        assert "mate" in text.lower()  # the compensation / mate question is there


def test_hanging_own_real_items_have_the_safe_and_unsafe_choice_their_label_needs():
    # A move can only be a miss (or a good choice) if there was a choice. Found in review:
    # 12 blunders had no safe alternative and 2 "safe" items had nothing that could hang.
    b = builder()
    for r in rows():
        if r["category"] not in ("real_blunder", "real_safe"):
            continue
        board = chess.Board(r["fen"])
        move = chess.Move.from_uci(r["move_uci"])
        flags = b.choice_flags(board)
        where = (r["id"], r["category"], r["fen"], r["move_uci"])
        if r["category"] == "real_blunder":
            assert flags[move] and any(not v for m, v in flags.items() if m != move), where
        else:
            assert not flags[move] and any(flags.values()), where


def test_real_blunders_are_labelled_by_the_engine_evidence_rule():
    b = builder()
    seen = set()
    for r in rows():
        if r["category"] != "real_blunder":
            continue
        seen.add(r["label"])
        assert {"engine_best_cp", "engine_after_cp", "loss_cp"} <= set(r)  # evidence kept for reproduction
        assert r["loss_cp"] == r["engine_best_cp"] - r["engine_after_cp"]
        if r["label"] == "missed":
            assert r["loss_cp"] >= b.MISS_LOSS_CP and r["material_label"] == "missed"
        else:  # it hangs a piece but the engine does not confirm a loss (found in review: rp1-080)
            assert r["label"] == "uncertain" and r["loss_cp"] < b.UNCERTAIN_LOSS_CP
            assert r["material_label"] == "missed"
    assert seen <= {"missed", "uncertain"}


def test_material_label_is_what_the_hand_check_validates():
    for r in rows():
        assert "material_label" in r
        if r["label"] != r["material_label"]:  # only an engine override may differ
            assert (r["detector"], r["label"], r["material_label"]) == ("hanging_own", "uncertain", "missed")


def test_adversarial_items_carry_engine_evidence_that_agrees_with_their_labels():
    b = builder()
    for r in rows():
        if r["category"] != "adversarial":
            continue
        assert {"engine_best_cp", "engine_after_cp", "loss_cp"} <= set(r)
        if r["label"] == "missed":
            assert r["loss_cp"] >= b.UNCERTAIN_LOSS_CP
