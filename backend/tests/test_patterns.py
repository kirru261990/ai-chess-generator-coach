import pytest

from app.learner import patterns as p

# White to move; Rd1 can take the loose knight on d5 (a free piece), or not.
FREE_KNIGHT = "4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1"
AFTER_TAKE = "4k3/8/8/3R4/8/8/8/4K3 b - - 0 1"
AFTER_IGNORE = "4k3/8/8/3n4/8/8/8/3R1K2 b - - 1 1"


def pos(fen, cp, ply=0):
    return {"ply": ply, "fen": fen, "cp": cp, "mate": None, "mate_sign": None, "best": "d1d5", "depth": 10}


def analysis(move, after_fen, cp_before, cp_after, schema=2):
    return {"schema": schema, "engine": "Stockfish test", "budget": {"depth": 10, "movetime_ms": None},
            "moves": [move], "sans": ["?"], "positions": [pos(FREE_KNIGHT, cp_before), pos(after_fen, cp_after, 1)]}


def outcomes(rows, name="missed_free"):
    return [r["outcomes"][name] for r in rows]


def test_taking_the_free_piece_is_taken():
    rows = p.classify_game({"user_color": "white"}, analysis("d1d5", AFTER_TAKE, 300, 500))
    assert outcomes(rows) == ["taken"] and rows[0]["ply"] == 0


def test_ignoring_it_with_a_confirmed_loss_is_missed():
    rows = p.classify_game({"user_color": "white"}, analysis("e1f1", AFTER_IGNORE, 300, 0))
    assert outcomes(rows) == ["missed"]


def test_ignoring_it_without_a_confirmed_loss_is_uncertain():
    rows = p.classify_game({"user_color": "white"}, analysis("e1f1", AFTER_IGNORE, 300, 280))
    assert outcomes(rows) == ["uncertain"]


def black_game(cp_before, cp_after, move):
    """White plays Ke1-e2, then Black (the user) can take a loose white knight on d4 with Rd7."""
    start = "4k3/3r4/8/8/3N4/8/8/4K3 w - - 0 1"
    black_to_move = "4k3/3r4/8/8/3N4/8/4K3/8 b - - 1 1"
    taken = "4k3/8/8/8/3r4/8/4K3/8 w - - 0 2"
    ignored = "3k4/3r4/8/8/3N4/8/4K3/8 w - - 2 2"
    return {"schema": 2, "engine": "x", "budget": {"depth": 10, "movetime_ms": None},
            "moves": ["e1e2", move], "sans": [],
            "positions": [pos(start, 0), pos(black_to_move, cp_before, 1),
                          pos(taken if move == "d7d4" else ignored, cp_after, 2)]}


def test_black_user_is_judged_only_on_their_own_moves_with_evidence_from_their_side():
    rows = p.classify_game({"user_color": "black"}, black_game(-300, -500, "d7d4"))  # White's view: Black gains
    assert [r["ply"] for r in rows] == [1] and outcomes(rows) == ["taken"]
    (_, _, _, evidence), = p.user_moves(black_game(-300, 0, "e8d8"), "black")
    assert (evidence.best_cp, evidence.after_cp) == (300, 0)  # the mover's side, not White's
    rows = p.classify_game({"user_color": "black"}, black_game(-300, 0, "e8d8"))
    assert outcomes(rows) == ["missed"]  # losing 300 from Black's side confirms the miss


def test_an_old_analysis_schema_is_refused():
    with pytest.raises(p.PatternError):
        p.classify_game({"user_color": "white"}, analysis("d1d5", AFTER_TAKE, 300, 500, schema=1))


def row(hanging="not_applicable", free="not_applicable"):
    return {"ply": 0, "outcomes": {"hanging_own": hanging, "missed_free": free}}


def test_uncertain_moves_leave_every_denominator():
    games = [[row(free="missed"), row(free="taken"), row(free="uncertain"), row()]]
    d = p.summarise(games)["detectors"]["missed_free"]
    assert d["counts"]["uncertain"] == 1 and d["opportunities"] == 2
    assert d["missed_of_available"]["k"] == 1 and d["missed_of_available"]["n"] == 2
    assert d["moves_counted"] == 3 and d["missed_per_100_moves"]["n"] == 3


def test_hanging_own_has_no_missed_of_available():
    d = p.summarise([[row(hanging="missed")]])["detectors"]["hanging_own"]
    assert "missed_of_available" not in d and d["missed_per_100_moves"]["k"] == 1


def test_labels_follow_the_spec_thresholds():
    assert p.label(2, 2, 20) == "insufficient"  # too few misses
    assert p.label(3, 1, 20) == "insufficient"  # all in one game
    assert p.label(3, 2, 7) == "tentative"
    assert p.label(3, 2, 8) == "established"


def test_wilson_interval_basics():
    assert p.wilson(0, 0) is None
    lo, hi = p.wilson(5, 10)
    assert 0.2 < lo < 0.5 < hi < 0.8


def window(ids_by_tc):
    return {"sha256": "x", "by_time_control": {tc: {"ids": ids} for tc, ids in ids_by_tc.items()}}


def synthetic_game(i, tc="600"):
    return {"source_id": f"https://www.chess.com/game/live/{i}", "user_color": "white", "time_control": tc}


def test_results_are_kept_per_time_control_and_a_missing_game_fails_closed():
    games = [synthetic_game(1), synthetic_game(2, "900+10")]
    analyses = {g["source_id"]: analysis("d1d5", AFTER_TAKE, 300, 500) for g in games}
    result = p.run(games, analyses, window({"10|0": ["1"], "15|10": ["2"]}))
    assert set(result["by_time_control"]) == {"10|0", "15|10"}
    assert result["by_time_control"]["10|0"]["games"] == 1
    with pytest.raises(p.PatternError):
        p.run(games, analyses, window({"10|0": ["1", "3"]}))
    with pytest.raises(p.PatternError):
        p.run(games, {}, window({"10|0": ["1"]}))
