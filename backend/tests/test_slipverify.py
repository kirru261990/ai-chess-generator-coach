"""Deeper engine check of first-slip drills (ADR 0020 hand-check replacement): does the slip and its answer set hold at a deeper search?"""

from types import SimpleNamespace as NS

import chess

from app.learner import drillbank, slipverify

START = chess.Board().fen()
DRILL = {"id": "d1", "fen": START, "played": "a2a3", "accepted": ["e2e4", "d2d4"], "game_id": "g1"}


def A(move, cp=None, mate=None):
    return NS(best_move=move, score=NS(cp=cp, mate=mate, mate_sign=(1 if (mate or 0) > 0 else -1) if mate else None), pv=(move,), depth=24)


class Fake:
    """A scripted engine: top lines for the position, and the score of the position after the played move (mover's view)."""

    def __init__(self, top, after):
        self.top, self.after, self.calls = top, after, []

    def analyse_multi(self, board, multipv, budget=None, perspective=None, new_game=False):
        self.calls.append(("multi", budget.depth))
        return self.top

    def analyse(self, board, budget=None, perspective=None):
        self.calls.append(("one", budget.depth))
        return self.after


def test_the_slip_holds_when_the_deeper_search_still_loses_150_and_the_best_move_is_an_accepted_one():
    got = slipverify.verify(DRILL, Fake([A("e2e4", 40), A("d2d4", 30), A("g1f3", 10)], A("e7e5", -300)), depth=24)
    assert got["slip_holds"] is True and got["answers_hold"] is True and got["loss_cp"] == 340 and got["verdict"] == "holds"


def test_a_deeper_search_that_finds_the_move_fine_fails_the_drill():
    got = slipverify.verify(DRILL, Fake([A("e2e4", 40)], A("e7e5", -60)), depth=24)  # loses only 100
    assert got["slip_holds"] is False and got["verdict"] == "slip_not_confirmed"


def test_the_slip_can_hold_while_the_deeper_best_move_is_not_in_the_accepted_set():
    got = slipverify.verify(DRILL, Fake([A("g1f3", 40), A("e2e4", 35)], A("e7e5", -300)), depth=24)
    assert got["slip_holds"] is True and got["answers_hold"] is False and got["verdict"] == "slip_holds_answers_differ"
    assert got["deep_best"] == "g1f3"


def test_a_position_decided_at_depth_still_confirms_a_big_loss_but_is_noted():
    got = slipverify.verify(DRILL, Fake([A("e2e4", 900)], A("e7e5", 500)), depth=24)
    assert got["slip_holds"] is True and got["decided_deep"] is True  # losing 400 from a won position is still a real slip


def test_a_mate_counts_as_a_huge_score():
    got = slipverify.verify(DRILL, Fake([A("e2e4", cp=50)], A("d8h4", mate=-1)), depth=24)
    assert got["slip_holds"] is True and got["loss_cp"] > 5000


def test_summary_reports_rates_with_denominators_and_the_30_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drillbank.bank_dir().mkdir(parents=True)
    rows = [{"id": f"s{n}", "verdict": "holds" if n < 28 else "slip_not_confirmed", "slip_holds": n < 28,
             "answers_hold": n < 25} for n in range(30)]
    got = slipverify.summarise(rows, gate=27, expected=30)
    assert got["of"] == 30 and got["slip_holds"] == 28 and got["answers_hold"] == 25 and got["gate"] == 27 and got["passed"] is True
    assert slipverify.summarise(rows[:29], gate=27, expected=30)["passed"] is False  # the gate is 27 of 30 and the set is incomplete
    assert "gate" not in slipverify.summarise(rows)  # no gate unless one is given (the full run has none)
