"""PRD v2 detectors (M1 = hanging_own v3, M2 = missed_free v3), the sound-move check and the CLEAN selector.

Engine results are scripted (`FakeAnalyser`), so each test pins down one rule. Scores in `L(...)` are from White's side, as the
evidence engine stores them. One test at the end uses the real engine at a shallow depth.
"""

import os
import shutil

import chess
import pytest

from app.db.schema import connect
from app.detectors import clean, hanging_own_v4, missed_free_v3, sound
from app.detectors import prd_rules as R
from app.engine.evidence import EngineConfig, EvidenceAnalyser, EvidenceAnalysis, Line

CFG = EngineConfig("Stockfish 19", "nn-test.nnue", "sha", depth=18, multipv=3, hash_mb=64, threads=1)


def L(move, cp=None, pv=None, mate=None, mate_sign=None):
    return Line(move, tuple(pv or (move,)), cp, mate, mate_sign, 18)


class FakeAnalyser:
    """Returns scripted lines by FEN; `overrides[(fen, depth)]` replaces them at one depth (e.g. the stability depth)."""

    config = CFG

    def __init__(self, scripts, overrides=None):
        self.scripts = scripts
        self.overrides = overrides or {}

    def analyse(self, board, depth=None):
        fen, d = board.fen(), depth or CFG.depth
        lines = self.overrides.get((fen, d), self.scripts.get(fen))
        if lines is None:
            raise KeyError(f"no script for {fen}")
        return EvidenceAnalysis(fen, CFG.at_depth(d).id, tuple(lines))


def after(fen, uci):
    b = chess.Board(fen)
    b.push_uci(uci)
    return b.fen()


def mv(uci):
    return chess.Move.from_uci(uci)


# --- M1: White plays Rh7?? and the queen takes the rook ------------------------------------------------------------------

M1_FEN = "4k3/4q3/8/8/8/8/3B4/6KR w - - 0 1"


def m1_scripts(**changes):
    s = {
        M1_FEN: [L("h1h2", -150), L("d2g5", -160), L("g1f2", -170)],
        after(M1_FEN, "h1h7"): [L("e7h7", -800, pv=("e7h7", "g1f1"))],
        after(M1_FEN, "h1h2"): [L("e7e6", -150)],
        after(M1_FEN, "d2g5"): [L("e7e6", -160)],
        after(M1_FEN, "g1f2"): [L("e7e6", -170)],
        after(M1_FEN, "h1h6"): [L("e7e6", -600)],
    }
    s.update(changes)
    return s


def test_m1_hanging_piece_is_a_mistake_with_a_full_evidence_record():
    f = hanging_own_v4.detect(chess.Board(M1_FEN), mv("h1h7"), 10, FakeAnalyser(m1_scripts()))
    assert (f.outcome, f.reason) == ("mistake", "all_checks_hold")
    e = f.evidence
    assert e["mistake_type"] == "M1" and e["fen"] == M1_FEN and e["ply"] == 10
    assert e["player_move"] == {"uci": "h1h7", "san": "Rh7"}
    assert e["best_move"] == {"uci": "h1h2", "san": "Rh2"}
    assert e["target_squares"] == ["h1"] and e["lost_piece"] == "moved" and e["lost_piece_square_after"] == "h7"
    assert e["refutation_line"] == {"uci": ["e7h7", "g1f1"], "san": ["Qxh7", "Kf1"]}
    assert e["material_swing"] == 5
    assert (e["eval_before"], e["eval_after"], e["eval_loss"], e["eval_loss_stability"]) == (-150, -800, 650, 650)
    assert e["engine_config_id"] == CFG.id and e["stability_config_id"] == CFG.stability.id
    assert (e["detector"], e["detector_version"], e["rules_version"]) == ("hanging_own", "4", R.RULES_VERSION)
    assert [a["uci"] for a in f.alternatives] == ["h1h2", "d2g5", "g1f2"]


def test_m1_counts_what_the_players_own_move_captured():
    """Owner's finding (Step 1c): taking a bishop and losing the rook for it is a trade (net 2), not a hanging piece."""
    fen = "4k3/3b4/8/8/8/8/8/3RK3 w - - 0 1"
    scripts = {fen: [L("e1e2", 50)], after(fen, "d1d7"): [L("e8d7", -300, pv=("e8d7",))]}
    f = hanging_own_v4.detect(chess.Board(fen), mv("d1d7"), 10, FakeAnalyser(scripts))
    assert (f.outcome, f.reason) == ("uncertain", "material_swing_below_minimum")


def test_m1_grabbing_a_pawn_and_losing_a_rook_is_still_a_hanging_piece():
    fen = "4k3/3p4/2b5/8/8/8/8/3RK3 w - - 0 1"
    scripts = {
        fen: [L("e1e2", 0), L("d1d2", 0), L("e1f2", 0)],
        after(fen, "d1d7"): [L("c6d7", -400, pv=("c6d7", "e1e2"))],
        after(fen, "e1e2"): [L("e8e7", 0)],
        after(fen, "d1d2"): [L("e8e7", 0)],
        after(fen, "e1f2"): [L("e8e7", 0)],
    }
    f = hanging_own_v4.detect(chess.Board(fen), mv("d1d7"), 10, FakeAnalyser(scripts))
    assert f.outcome == "mistake"
    assert (f.evidence["material_swing"], f.evidence["swing_after_move"]) == (4, 5)  # rook 5 minus the pawn 1
    assert f.evidence["refutation_line"]["uci"] == ["c6d7", "e1e2"]
    again = sound.check_move(chess.Board(fen), mv("d1d7"), f.evidence, FakeAnalyser(scripts))
    assert "refutation_still_wins" in again.failed


def test_m1_target_is_the_piece_left_behind_when_another_move_was_played():
    # Black to move: the knight on c6 is attacked by the bishop; Black plays a king move and loses it.
    fen = "r5k1/8/2n5/1B6/8/8/8/4K3 b - - 0 1"
    scripts = {
        fen: [L("c6e5", 0), L("c6d4", 0), L("a8a5", 0)],
        after(fen, "g8g7"): [L("b5c6", 400, pv=("b5c6", "g7f6"))],
        after(fen, "c6e5"): [L("e1d2", 0)],
        after(fen, "c6d4"): [L("e1d2", 0)],
        after(fen, "a8a5"): [L("b5c6", 0)],
    }
    f = hanging_own_v4.detect(chess.Board(fen), mv("g8g7"), 11, FakeAnalyser(scripts))
    assert f.outcome == "mistake"
    assert f.evidence["target_squares"] == ["c6"] and f.evidence["lost_piece"] == "other"


@pytest.mark.parametrize(
    ("ply", "scripts", "expected"),
    [
        (4, m1_scripts(), ("skipped", "before_min_ply")),
        (10, m1_scripts(**{M1_FEN: [L("h1h2", -700)]}), ("skipped", "decided")),
        (10, m1_scripts(**{after(M1_FEN, "h1h7"): [L("e7h7", -300, pv=("e7h7",))]}),
         ("no_mistake", "loss_below_threshold")),
        (10, m1_scripts(**{after(M1_FEN, "h1h7"): [L("e7e6", -800)]}),
         ("uncertain", "top_line_not_a_capture_of_player_piece")),
    ],
)
def test_m1_gates_and_thresholds(ply, scripts, expected):
    f = hanging_own_v4.detect(chess.Board(M1_FEN), mv("h1h7"), ply, FakeAnalyser(scripts))
    assert (f.outcome, f.reason) == expected and f.evidence is None


def test_m1_loss_must_hold_at_the_stability_depth():
    overrides = {(after(M1_FEN, "h1h7"), CFG.stability.depth): [L("e7h7", -300, pv=("e7h7",))]}
    f = hanging_own_v4.detect(chess.Board(M1_FEN), mv("h1h7"), 10, FakeAnalyser(m1_scripts(), overrides))
    assert (f.outcome, f.reason) == ("uncertain", "loss_not_stable")


def test_m1_refutation_that_loses_material_back_is_not_a_mistake():
    fen = "4k3/4q3/8/8/8/3B4/8/6KR w - - 0 1"  # a bishop on d3 guards h7
    scripts = {fen: [L("h1h2", -150)], after(fen, "h1h7"): [L("e7h7", -800, pv=("e7h7", "d3h7"))]}
    f = hanging_own_v4.detect(chess.Board(fen), mv("h1h7"), 10, FakeAnalyser(scripts))
    assert (f.outcome, f.reason) == ("uncertain", "material_swing_below_minimum")


def test_m1_needs_a_sound_move_or_the_piece_was_lost_anyway():
    bad = {after(M1_FEN, u): [L("e7e6", -500)] for u in ("h1h2", "d2g5", "g1f2")}
    f = hanging_own_v4.detect(chess.Board(M1_FEN), mv("h1h7"), 10, FakeAnalyser(m1_scripts(**bad)))
    assert (f.outcome, f.reason) == ("uncertain", "no_sound_move")


def test_only_legal_move_is_skipped():
    fen = "7k/8/8/8/8/5q2/8/6K1 w - - 0 1"  # Kh2 is the only move
    f = hanging_own_v4.detect(chess.Board(fen), mv("g1h2"), 20, FakeAnalyser({fen: [L("g1h2", -900)]}))
    assert (f.outcome, f.reason) == ("skipped", "only_legal_move")


def test_illegal_move_is_refused():
    with pytest.raises(ValueError):
        hanging_own_v4.detect(chess.Board(M1_FEN), mv("h1g1"), 10, FakeAnalyser(m1_scripts()))


# --- M2: White can take a loose rook on h5 -------------------------------------------------------------------------

M2_FEN = "4k3/8/8/7r/8/8/8/3QK3 w - - 0 1"


def m2_scripts(**changes):
    s = {
        M2_FEN: [L("d1h5", 600, pv=("d1h5", "e8d7")), L("d1d2", 0), L("e1f1", -10)],
        after(M2_FEN, "d1h5"): [L("e8d7", 600)],
        after(M2_FEN, "d1d2"): [L("h5h2", 0)],
        after(M2_FEN, "e1f1"): [L("e8d7", 0)],
    }
    s.update(changes)
    return s


def test_m2_missed_free_capture_is_a_mistake():
    f = missed_free_v3.detect(chess.Board(M2_FEN), mv("e1f1"), 12, FakeAnalyser(m2_scripts()))
    assert (f.outcome, f.reason) == ("missed", "all_checks_hold")
    e = f.evidence
    assert e["mistake_type"] == "M2" and e["target_squares"] == ["h5"]
    assert e["free_captures"] == [{"uci": "d1h5", "san": "Qxh5+"}]
    assert e["refutation_line"] == {"uci": ["d1h5", "e8d7"], "san": ["Qxh5+", "Kd7"]}
    assert e["material_swing"] == 5 and e["eval_loss"] == 600
    assert (e["detector"], e["detector_version"]) == ("missed_free", "3")
    assert [a["uci"] for a in f.alternatives] == ["d1h5"]


def test_m2_taking_the_piece_counts_as_taken():
    f = missed_free_v3.detect(chess.Board(M2_FEN), mv("d1h5"), 12, FakeAnalyser(m2_scripts()))
    assert (f.outcome, f.reason) == ("taken", "played_a_free_capture")


def test_m2_capture_may_be_an_equal_alternative_to_the_best_move():
    within = {M2_FEN: [L("d1d2", 410), L("d1h5", 400, pv=("d1h5", "e8d7")), L("e1f1", -10)]}
    assert missed_free_v3.detect(chess.Board(M2_FEN), mv("e1f1"), 12, FakeAnalyser(m2_scripts(**within))).outcome == "missed"
    beyond = {M2_FEN: [L("d1d2", 450), L("d1h5", 400, pv=("d1h5", "e8d7")), L("e1f1", -10)]}
    f = missed_free_v3.detect(chess.Board(M2_FEN), mv("e1f1"), 12, FakeAnalyser(m2_scripts(**beyond)))
    assert (f.outcome, f.reason) == ("not_available", "no_free_capture_in_best_lines")


def test_m2_small_or_unstable_loss_is_uncertain():
    small = {after(M2_FEN, "e1f1"): [L("e8d7", 500)]}
    f = missed_free_v3.detect(chess.Board(M2_FEN), mv("e1f1"), 12, FakeAnalyser(m2_scripts(**small)))
    assert (f.outcome, f.reason) == ("uncertain", "loss_below_threshold")
    overrides = {(after(M2_FEN, "e1f1"), CFG.stability.depth): [L("e8d7", 500)]}
    f = missed_free_v3.detect(chess.Board(M2_FEN), mv("e1f1"), 12, FakeAnalyser(m2_scripts(), overrides))
    assert (f.outcome, f.reason) == ("uncertain", "loss_not_stable")


def test_m2_capture_that_loses_material_back_is_not_free():
    fen = "4k3/8/6p1/7r/8/8/8/3QK3 w - - 0 1"  # the g6 pawn guards h5: Qxh5 gxh5 loses the queen for a rook
    scripts = {fen: [L("d1h5", 300, pv=("d1h5", "g6h5")), L("d1d2", 0), L("e1f1", 0)]}
    f = missed_free_v3.detect(chess.Board(fen), mv("e1f1"), 12, FakeAnalyser(scripts))
    assert (f.outcome, f.reason) == ("not_available", "no_free_capture_in_best_lines")


# --- Sound move -----------------------------------------------------------------------------------------------------

def m1_evidence():
    return hanging_own_v4.detect(chess.Board(M1_FEN), mv("h1h7"), 10, FakeAnalyser(m1_scripts())).evidence


def test_sound_accepts_any_move_that_meets_the_rules_not_only_the_best():
    analyser = FakeAnalyser(m1_scripts())
    for uci in ("h1h2", "g1f2"):
        assert sound.check_move(chess.Board(M1_FEN), mv(uci), m1_evidence(), analyser).sound


def test_sound_rejects_repeating_the_mistake_and_a_big_loss():
    analyser = FakeAnalyser(m1_scripts())
    again = sound.check_move(chess.Board(M1_FEN), mv("h1h7"), m1_evidence(), analyser)
    assert not again.sound and again.failed == ("refutation_still_wins", "eval_loss_too_large")
    elsewhere = sound.check_move(chess.Board(M1_FEN), mv("h1h6"), m1_evidence(), analyser)
    assert elsewhere.failed == ("eval_loss_too_large",) and elsewhere.eval_loss == 450


def test_sound_m2_capture_or_small_loss():
    analyser = FakeAnalyser(m2_scripts(**{after(M2_FEN, "e1f1"): [L("e8d7", 540)]}))
    evidence = missed_free_v3.detect(chess.Board(M2_FEN), mv("e1f1"), 12, FakeAnalyser(m2_scripts())).evidence
    board = chess.Board(M2_FEN)
    assert sound.check_move(board, mv("d1h5"), evidence, analyser).sound
    assert sound.check_move(board, mv("e1f1"), evidence, analyser).sound  # not the capture, but loses only 60
    missed = sound.check_move(board, mv("d1d2"), evidence, analyser)
    assert missed.failed == ("free_piece_not_taken", "eval_loss_too_large")


def test_sound_refuses_an_illegal_move_or_another_position():
    with pytest.raises(ValueError):
        sound.check_move(chess.Board(M1_FEN), mv("h1g1"), m1_evidence(), FakeAnalyser(m1_scripts()))
    with pytest.raises(ValueError):
        sound.check_move(chess.Board(), mv("e2e4"), m1_evidence(), FakeAnalyser(m1_scripts()))


# --- CLEAN ----------------------------------------------------------------------------------------------------------

CLEAN_FEN = "4k3/8/8/3p4/4N3/5P2/8/4K3 w - - 0 1"  # the knight is attacked but defended: nothing to win or lose


def clean_scripts(after_cp=20):
    return {CLEAN_FEN: [L("e4c5", 20, pv=("e4c5", "e8d8"))], after(CLEAN_FEN, "e4c5"): [L("e8d8", after_cp)]}


def test_clean_position_has_an_attacked_piece_and_no_threat():
    f = clean.detect(chess.Board(CLEAN_FEN), mv("e4c5"), 10, FakeAnalyser(clean_scripts()))
    assert (f.outcome, f.reason) == ("clean", "all_checks_hold")
    assert f.evidence["answer"] == "no_immediate_threat" and f.evidence["attacked_squares"] == ["e4"]
    assert f.evidence["eval_loss"] == 0 and f.evidence["engine_config_id"] == CFG.id


def test_clean_needs_a_near_best_move():
    f = clean.detect(chess.Board(CLEAN_FEN), mv("e4c5"), 10, FakeAnalyser(clean_scripts(after_cp=-10)))
    assert (f.outcome, f.reason) == ("not_clean", "move_not_sound_enough")


@pytest.mark.parametrize(
    ("fen", "reason"),
    [
        (chess.STARTING_FEN, "nothing_attacked"),
        (M2_FEN, "player_has_free_capture"),
        ("4k3/8/8/3p4/4N3/8/8/4K3 w - - 0 1", "player_piece_can_be_won"),
        ("4k3/8/8/p7/1b6/3N4/8/4K3 w - - 0 1", "in_check"),
        (CLEAN_FEN, None),
    ],
)
def test_clean_static_rules(fen, reason):
    assert clean.static_reason(chess.Board(fen)) == reason


# --- shared measurements ----------------------------------------------------------------------------------------------

def test_line_swing_counts_material_and_the_losing_sides_recapture():
    board = chess.Board(after("4k3/4q3/8/8/8/3B4/8/6KR w - - 0 1", "h1h7"))
    assert R.line_swing(board, ("e7h7",), chess.BLACK) == (5 - 9, 1)  # the bishop takes the queen back
    board = chess.Board(after(M1_FEN, "h1h7"))
    assert R.line_swing(board, ("e7h7", "g1f1"), chess.BLACK) == (5, 2)
    assert R.line_swing(board, ("e7h7", "h8h1"), chess.BLACK) == (5, 1)  # stops at an illegal move


def test_line_swing_never_counts_beyond_the_ply_limit():
    board = chess.Board("4k3/8/8/8/8/8/1r5r/R3K2R w - - 0 1")
    pv = ("a1a8", "e8e7", "a8a7", "e7e6", "h1h2")  # the rook capture on h2 is ply 5
    assert R.line_swing(board, pv, chess.WHITE) == (0, 4)


def test_mate_scores_count_as_large_but_finite():
    assert R.line_score(L("a1a2", mate=3, mate_sign=1), chess.WHITE) == R.MATE_CP
    assert R.line_score(L("a1a2", mate=-2, mate_sign=-1), chess.WHITE) == -R.MATE_CP
    assert R.line_score(L("a1a2", cp=5000), chess.BLACK) == -R.MATE_CP


# --- real engine, shallow ---------------------------------------------------------------------------------------------

@pytest.mark.skipif(not (os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")), reason="Stockfish not installed")
def test_real_engine_finds_the_hanging_rook():
    from app.engine.stockfish import Engine

    with Engine() as engine:
        cfg = EngineConfig(engine.name, "test", "test", depth=12, multipv=3, hash_mb=16, threads=1)
        analyser = EvidenceAnalyser(engine, cfg, connect(":memory:"))
        board = chess.Board(M1_FEN)
        f = hanging_own_v4.detect(board, mv("h1h7"), 10, analyser)
        assert f.outcome == "mistake", f
        assert f.evidence["refutation_line"]["uci"][0] == "e7h7" and f.evidence["material_swing"] >= 5
        assert f.alternatives
