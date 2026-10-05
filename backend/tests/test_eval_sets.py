import json
from pathlib import Path

import chess

SET = Path(__file__).resolve().parents[2] / "evals" / "sets" / "hanging_own_v1" / "positions.jsonl"


def rows():
    return [json.loads(line) for line in SET.read_text().splitlines() if line.strip()]


def test_hanging_own_set_is_well_formed():
    data = rows()
    assert len(data) == 50
    assert len({r["id"] for r in data}) == 50 and len({(r["fen"], r["move_uci"]) for r in data}) == 50
    assert {r["label"] for r in data} == {"missed", "taken"}
    assert sum(r["label"] == "missed" for r in data) == 25
    for r in data:
        board = chess.Board(r["fen"])
        assert board.is_valid()
        move = chess.Move.from_uci(r["move_uci"])
        assert move in board.legal_moves and board.san(move) == r["move_san"]
        assert r["side_to_move"] == ("white" if board.turn else "black")
        assert r["net_material"] <= -2 if r["label"] == "missed" else r["net_material"] > -2


MISSED_FREE = SET.parent.parent / "missed_free_v1" / "positions.jsonl"


def test_missed_free_set_is_well_formed():
    data = [json.loads(line) for line in MISSED_FREE.read_text().splitlines() if line.strip()]
    assert len(data) == 50 and len({r["id"] for r in data}) == 50
    assert len({(r["fen"], r["move_uci"]) for r in data}) == 50
    counts = {label: sum(r["label"] == label for r in data) for label in {r["label"] for r in data}}
    assert counts == {"missed": 25, "taken": 15, "not_applicable": 10}
    for r in data:
        board = chess.Board(r["fen"])
        assert board.is_valid()
        move = chess.Move.from_uci(r["move_uci"])
        assert move in board.legal_moves and board.san(move) == r["move_san"]
        assert r["side_to_move"] == ("white" if board.turn else "black")
        if r["label"] == "missed":
            assert r["loss_cp"] >= 100 and r["net_material_best"] >= 2
        if r["label"] == "taken":
            assert r["loss_cp"] < 100 and r["net_material_best"] >= 2
