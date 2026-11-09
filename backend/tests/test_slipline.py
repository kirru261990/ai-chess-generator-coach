"""Engine lines for the review screen (ADR 0021 decision 7): up to 6 moves for the played move and for the better move, stored per drill."""

from types import SimpleNamespace as NS

import chess
import pytest

from app.learner import drillbank, slipline

QFEN = "4k3/8/2p5/3p4/8/8/3Q4/4K3 w - - 0 1"  # White's queen can take the d5 pawn; a pawn takes it back
DRILL = {"id": "q1", "fen": QFEN, "played": "d2d5", "accepted": ["e1f1"], "game_id": "g"}


class Line:
    def __init__(self, pv):
        self.move, self.pv = pv[0], tuple(pv)


class Scripted:
    config = NS(id="ec-test")

    def __init__(self, table):
        self.table = table

    def analyse(self, board, depth=None):
        return NS(best=Line(self.table[board.fen()]))


def after(fen, uci):
    b = chess.Board(fen)
    b.push_uci(uci)
    return b.fen()


def engine():
    return Scripted({after(QFEN, "d2d5"): ["c6d5", "e1f1", "e8e7", "f1e2"], after(QFEN, "e1f1"): ["e8e7", "f1e2", "e7d6", "e2d3", "d6c5"]})


def test_each_line_starts_with_the_move_and_follows_the_engines_reply_up_to_six_moves():
    got = slipline.lines_for(DRILL, engine())
    assert got["mine"] == ["d2d5", "c6d5", "e1f1", "e8e7", "f1e2"] and got["engine_config"] == "ec-test" and got["plies"] == 6
    assert got["better"] == ["e1f1", "e8e7", "f1e2", "e7d6", "e2d3", "d6c5"]  # six moves: three for each side
    assert len(slipline.lines_for(DRILL, engine())["better"]) == slipline.PLIES == 6


def test_steps_name_who_moves_and_count_your_points_as_the_line_plays():
    steps = slipline.steps(QFEN, ["d2d5", "c6d5", "e1f1", "e8e7"])
    assert [s["who"] for s in steps] == ["you", "they", "you", "they"]
    assert [s["san"] for s in steps] == ["Qxd5", "cxd5", "Kf1", "Ke7"]
    assert [s["points"] for s in steps] == [1, -8, -8, -8]
    b = chess.Board(QFEN)
    b.push_uci("d2d5")
    assert steps[0]["fen"] == b.fen()  # each step carries the position after its move, so the screen needs no chess rules of its own  # you take a pawn (+1), they take the queen (-9), nothing else changes


def test_a_move_that_ends_the_game_stops_the_line_and_the_engine_is_not_asked():
    mate = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"  # Qg7 is checkmate
    got = slipline.lines_for({"id": "m", "fen": mate, "played": "f7g7", "accepted": []}, Scripted({}))
    assert got["mine"] == ["f7g7"] and got["better"] == []


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drillbank.bank_dir().mkdir(parents=True)


def test_lines_are_saved_whole_and_read_back_only_for_the_current_engine_config(folder):
    slipline.save({"a": {"mine": ["d2d5"], "better": ["e1f1"], "engine_config": "ec-test", "plies": 6},
                   "b": {"mine": ["d2d5"], "better": ["e1f1"], "engine_config": "ec-old", "plies": 6},
                   "c": {"mine": ["d2d5"], "better": ["e1f1"], "engine_config": "ec-test", "plies": 4},  # built with another line length
                   "d": {"mine": ["d2d5"], "better": ["e1f1"], "engine_config": "ec-test"}})  # made before the line length was recorded
    assert set(slipline.load("ec-test")) == {"a"}
    assert [p.name for p in slipline.lines_path().parent.glob("slip_lines*")] == ["slip_lines_v1.json"]
    slipline.lines_path().write_text("{not json")
    assert slipline.load("ec-test") == {}  # unreadable lines read as no lines: an answer must never fail because of this file


def test_the_review_holds_both_lines_with_the_start_position_and_is_none_without_stored_lines(folder):
    assert slipline.review(DRILL, {}) is None
    stored = {"mine": ["d2d5", "c6d5"], "better": ["e1f1", "e8e7"], "engine_config": "ec-test"}
    got = slipline.review(DRILL, stored)
    assert got["start_fen"] == QFEN and set(got) == {"start_fen", "mine", "better"}
    assert got["mine"][1] == {"uci": "c6d5", "san": "cxd5", "who": "they", "points": -8, "fen": after(after(QFEN, "d2d5"), "c6d5")}
