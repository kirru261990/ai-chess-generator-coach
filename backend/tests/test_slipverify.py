"""Deeper engine check of first-slip drills (ADR 0020 hand-check replacement): does the slip and its answer set hold at a deeper search?"""

import json
from types import SimpleNamespace as NS

import chess
import pytest

from app.learner import drillbank, slipfinder, slipverify

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


def sample_drill(n, source="own", game=None):
    return {"id": f"s{n:03d}", "source": source, "game_id": game or f"g{n}", "fen": START, "played": "a2a3", "accepted": ["e2e4"],
            "versions": {"slip_finder": slipfinder.VERSION, "bank": slipfinder.BANK_VERSION}}


def test_the_sample_is_30_own_drills_one_per_game_chosen_by_a_hash_not_by_the_order_of_the_bank():
    drills = [sample_drill(n) for n in range(80)] + [sample_drill(900, source="lichess"), sample_drill(901, game="g1")]
    s = slipverify.sample(drills)
    assert len(s) == 30 and len({d["game_id"] for d in s}) == 30 and {d["source"] for d in s} == {"own"}
    assert slipverify.sample(list(reversed(drills))) == s
    assert len(slipverify.sample(drills[:12])) == 12  # fewer than 30 available: all of them, and the caller sees the shortfall



def test_exclusions_list_the_drills_whose_slip_did_not_hold_and_are_saved_whole(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drillbank.bank_dir().mkdir(parents=True)
    rows = [{"id": "a", "slip_holds": True, "verdict": "holds", "depth": 24}, {"id": "b", "slip_holds": False, "verdict": "slip_not_confirmed", "depth": 24}]
    got = slipverify.exclusions(rows)
    assert got == {"b": {"reason": "slip_not_confirmed_at_depth_24"}}
    slipverify.save_exclusions(got)
    assert json.loads(slipverify.excluded_path().read_text()) == got


def test_the_sample_does_not_change_after_a_drill_is_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drillbank.bank_dir().mkdir(parents=True)
    drills = [sample_drill(n) for n in range(60)]
    for d in drills:
        d["evidence"], d["ply"] = {}, 8
        d["versions"]["engine_config"] = "ec"
    slipround_path = drillbank.bank_dir() / "slips_v1.jsonl"
    slipround_path.write_text("".join(json.dumps(d) + "\n" for d in drills))
    before = [d["id"] for d in slipverify.sample_drills()]
    slipverify.save_exclusions({before[0]: {"reason": "slip_not_confirmed_at_depth_24"}})
    assert [d["id"] for d in slipverify.sample_drills()] == before  # the same 30, including the one that failed


def test_a_half_written_last_line_in_the_results_file_does_not_stop_a_report_or_a_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drillbank.bank_dir().mkdir(parents=True)
    good = {"id": "a", "slip_holds": True, "answers_hold": True, "verdict": "holds", "depth": 24}
    slipverify.results_path(24).write_text(json.dumps(good) + "\n" + '{"id": "b", "slip_ho')
    assert list(slipverify._load(24)) == ["a"]


def test_a_move_that_ends_the_game_is_not_searched_and_is_never_a_slip():
    mate = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"  # Qg7 is checkmate
    got = slipverify.verify({"id": "m", "fen": mate, "played": "f7g7", "accepted": ["f7f8"], "game_id": "g"}, Fake([A("f7f8", 900)], None), depth=24)
    assert got["slip_holds"] is False and got["played_cp"] == slipverify.MATE_CP


def test_the_rows_say_which_engine_and_settings_made_them():
    class Named(Fake):
        name = "Stockfish test"

    got = slipverify.verify(DRILL, Named([A("e2e4", 40)], A("e7e5", -300)), depth=24)
    assert got["engine"] == "Stockfish test" and got["hash_mb"] == slipverify.HASH_MB and got["threads"] == slipverify.THREADS


def test_exclude_refuses_a_corrupt_file_rather_than_erasing_it_and_a_search_shallower_than_the_check(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drillbank.bank_dir().mkdir(parents=True)
    slipverify.excluded_path().write_text("{not json")
    with pytest.raises(SystemExit):
        slipverify.main(["exclude"])
    assert slipverify.excluded_path().read_text() == "{not json"
    with pytest.raises(SystemExit):
        slipverify.main(["exclude", "--depth", "18"])
