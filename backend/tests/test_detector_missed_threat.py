"""M3 missed threat (`missed_threat` v2, ADR 0011 and 0013) and its rules-only labels (`threat_kind`).

Engine results are scripted (`FakeAnalyser`), so each test pins down one rule. Scores in `L(...)` are from White's side, as the
evidence engine stores them. The positions are real openings, so each example can be set up on a board:

- RUY: 1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 b5, White to move (ply 8). 4...b5 attacks the bishop. 5.O-O?? misses it, 5.Bb3 meets it.
- SCHOLAR: 1.e4 e5 2.Qh5 Nc6 3.Bc4, Black to move (ply 5). Qxf7 is mate. 3...Nf6?? misses it (ADR 0011 decision 1: ply 4 start).
- KNIGHT: 1.e4 Nc6 2.Nf3 Nf6 3.e5, Black to move (ply 5). 3...d6?? loses the knight for a pawn, net 2 (decision 2).
One test at the end uses the real engine at a shallow depth.
"""

import os
import shutil

import chess
import pytest

from app.db.schema import connect
from app.detectors import missed_threat as MT
from app.detectors import prd_rules as R
from app.detectors import threat_kind as TK
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
        self.calls = 0

    def analyse(self, board, depth=None):
        self.calls += 1
        fen, d = board.fen(), depth or CFG.depth
        lines = self.overrides.get((fen, d), self.scripts.get(fen))
        if lines is None:
            raise KeyError(f"no script for {fen}")
        return EvidenceAnalysis(fen, CFG.at_depth(d).id, tuple(lines))


def play(*sans):
    b = chess.Board()
    for san in sans:
        b.push_san(san)
    return chess.Board(b.fen())  # positions are analysed without history, as the evidence engine does


def after(fen, uci):
    b = chess.Board(fen)
    b.push_uci(uci)
    return b.fen()


def passed(fen):
    return MT.passed_position(chess.Board(fen)).fen()


def forced(fen, move, threat):
    """The position after the player's `move` and then the opponent's `threat` move (the forced-threat loss is measured here)."""
    return after(after(fen, move), threat)


def mv(uci):
    return chess.Move.from_uci(uci)


# --- RUY: a new capture threat -----------------------------------------------------------------------------------------

RUY_MOVES = ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "b5")
RUY = play(*RUY_MOVES).fen()
RUY_PREV = play(*RUY_MOVES[:-1]).fen()  # before 4...b5, Black to move
RUY_PLY = 8


def ruy_scripts(**changes):
    s = {
        RUY: [L("a4b3", 20), L("a4c2", -10), L("h2h3", -290, pv=("h2h3", "b5a4"))],
        passed(RUY): [L("b5a4", -300, pv=("b5a4", "d2d3"))],
        after(RUY, "e1g1"): [L("b5a4", -290, pv=("b5a4", "d2d3"))],
        after(RUY, "a4b3"): [L("g8f6", 20)],
        after(RUY, "d2d4"): [L("b5a4", -60, pv=("b5a4", "d4e5"))],
        forced(RUY, "e1g1", "b5a4"): [L("d2d3", -290)],  # the bishop is lost: the threat explains the whole loss
    }
    s.update(changes)
    return s


def ruy(move, scripts=None, overrides=None, previous=RUY_PREV):
    prev = chess.Board(previous) if previous else None
    return MT.detect(chess.Board(RUY), mv(move), RUY_PLY, FakeAnalyser(scripts or ruy_scripts(), overrides), prev)


def test_castling_into_the_pawn_attack_is_a_missed_threat_with_a_full_record():
    f = ruy("e1g1")
    assert (f.outcome, f.reason) == ("missed", "all_checks_hold")
    e = f.evidence
    assert e["mistake_type"] == "M3" and e["fen"] == RUY and e["ply"] == RUY_PLY
    assert e["opponent_last_move"] == {"uci": "b7b5", "san": "b5"}
    assert e["threat_move"] == {"uci": "b5a4", "san": "bxa4"}
    assert (e["threat_kind"], e["threat_origin"]) == ("capture", "new")
    assert e["threat_material"] >= 2 and e["threat_mates"] is False
    assert e["threat_size_cp"] == 320  # +20 with Bb3, -300 after a pass
    assert e["player_move"] == {"uci": "e1g1", "san": "O-O"}
    assert e["best_move"] == {"uci": "a4b3", "san": "Bb3"}
    assert (e["eval_before"], e["eval_after"], e["eval_loss"], e["eval_loss_stability"]) == (20, -290, 310, 310)
    assert e["threat_after_move"] == "works"
    assert e["target_squares"] == ["a4"]
    assert (e["detector"], e["detector_version"], e["rules_version"]) == ("missed_threat", "2", R.RULES_VERSION)
    assert (e["ftl"], e["ftl_config_id"]) == (310, CFG.id)
    assert e["m3_thresholds"]["ftl_min_share"] == 0.5
    assert e["m3_thresholds"]["material_min"] == 2 and e["m3_thresholds"]["min_ply"] == 4
    assert e["engine_config_id"] == CFG.id and e["stability_config_id"] == CFG.stability.id
    assert [a["uci"] for a in f.alternatives] == ["a4b3", "a4c2"]  # h3 loses the bishop too


def test_moving_the_bishop_away_meets_the_threat():
    f = ruy("a4b3")
    assert (f.outcome, f.reason) == ("met", "defended")
    assert f.evidence["threat_after_move"] == "stopped"


def test_ignoring_the_threat_for_something_almost_as_good_is_countered():
    # 5.d4: Black can still take the bishop, but White wins the e5 pawn back and the score holds (loss 80 < 150).
    f = ruy("d2d4")
    assert (f.outcome, f.reason) == ("met", "countered")
    assert f.evidence["eval_loss"] == 80


def test_stopping_the_threat_but_losing_for_another_reason_is_not_a_missed_threat():
    f = ruy("a4b3", ruy_scripts(**{after(RUY, "a4b3"): [L("g8f6", -300)]}))
    assert (f.outcome, f.reason) == ("met", "defended_other_loss")


def test_loss_that_does_not_hold_at_the_stability_depth_is_uncertain():
    over = {(after(RUY, "e1g1"), CFG.stability.depth): [L("b5a4", -50, pv=("b5a4", "d2d3"))]}
    f = ruy("e1g1", overrides=over)
    assert (f.outcome, f.reason) == ("uncertain", "loss_not_stable")


def test_small_threat_the_best_move_stops_is_no_threat():
    f = ruy("e1g1", ruy_scripts(**{RUY: [L("a4b3", -200), L("a4c2", -210)]}))
    assert (f.outcome, f.reason) == ("no_threat", "passing_costs_little")
    assert f.evidence is None


def test_threat_the_best_move_cannot_stop_is_unavoidable_not_missed():
    f = ruy("e1g1", ruy_scripts(**{RUY: [L("h2h3", -280, pv=("h2h3", "b5a4"))]}))
    assert (f.outcome, f.reason) == ("uncertain", "threat_unavoidable")


def test_no_concrete_threat_when_a_pass_wins_nothing():
    f = ruy("e1g1", ruy_scripts(**{passed(RUY): [L("g8f6", 0)]}))
    assert (f.outcome, f.reason) == ("no_threat", "no_concrete_threat")


def test_origin_is_unknown_without_the_previous_position():
    f = ruy("e1g1", previous=None)
    assert f.outcome == "missed"
    assert f.evidence["threat_origin"] == "unknown" and "opponent_last_move" not in f.evidence


def test_a_threat_ignored_on_an_earlier_move_is_standing():
    # 5.d3?? and Black did not take: on White's 6th move the same bxa4 already worked a move ago.
    prev = play(*RUY_MOVES, "d3").fen()
    assert TK.origin(chess.Board(prev), ("b5a4",)) == "standing"
    assert TK.origin(chess.Board(RUY_PREV), ("b5a4",)) == "new"


# --- v2: the threat must explain the loss (ADR 0013) ---------------------------------------------------------------------

def ruy_with_forced_score(white_cp):
    return ruy("e1g1", ruy_scripts(**{forced(RUY, "e1g1", "b5a4"): [L("d2d3", white_cp)]}))


def test_a_loss_the_threat_does_not_explain_is_uncertain_not_missed():
    # The move still loses 310 cp and bxa4 still works, but after bxa4 White stands fine (+20): the loss came from elsewhere.
    f = ruy_with_forced_score(10)
    assert (f.outcome, f.reason) == ("uncertain", "loss_not_from_threat")
    assert f.evidence["ftl"] == 10 and f.evidence["eval_loss"] == 310


def test_a_threat_that_backfires_on_the_opponent_is_uncertain_and_the_ftl_is_negative():
    # The hc3-29 pattern: executing the threat is bad for the opponent (the owner judged the flag real; the rule abstains).
    f = ruy_with_forced_score(300)
    assert (f.outcome, f.reason) == ("uncertain", "loss_not_from_threat") and f.evidence["ftl"] == -280


def test_the_threat_must_explain_at_least_half_of_the_loss():
    assert ruy_with_forced_score(-135).outcome == "missed"  # ftl 155 = half of 310
    f = ruy_with_forced_score(-134)  # ftl 154
    assert (f.outcome, f.reason) == ("uncertain", "loss_not_from_threat")


def test_the_threat_must_also_cost_the_eval_loss_minimum():
    # The loss is 280 cp and the threat costs 140: exactly half, but under the 150 cp minimum, so uncertain.
    scripts = ruy_scripts(**{after(RUY, "e1g1"): [L("b5a4", -260, pv=("b5a4", "d2d3"))],
                             forced(RUY, "e1g1", "b5a4"): [L("d2d3", -120)]})
    f = ruy("e1g1", scripts)
    assert (f.outcome, f.reason) == ("uncertain", "loss_not_from_threat") and f.evidence["ftl"] == 140


def test_other_winning_replies_do_not_matter_only_the_forced_threat_does():
    # After the forced bxa4 the engine may prefer anything (scripted: a different best move); only the score counts.
    f = ruy("e1g1", ruy_scripts(**{forced(RUY, "e1g1", "b5a4"): [L("h2h3", -300), L("d2d3", -310)]}))
    assert f.outcome == "missed" and f.evidence["ftl"] == 320


def test_a_forced_threat_that_mates_needs_no_engine_call():
    # Scholar's mate: after ...Nf6?? Qxf7# the game is over, so the loss is scored as a mate without a search.
    a = FakeAnalyser(scholar_scripts())
    f = MT.detect(chess.Board(SCHOLAR), mv("g8f6"), 5, a, chess.Board(SCHOLAR_PREV))
    assert f.outcome == "missed" and f.evidence["ftl"] == R.MATE_CP


def test_a_stopped_threat_never_reaches_the_forced_threat_check():
    a = ruy("a4b3")
    assert a.outcome == "met" and "ftl" not in a.evidence


# --- the threat line after the player's move (PR 96 review) ------------------------------------------------------------

# Back rank: White threatens Rd8+ Rxd8 Rxd8#. Black plays ...Rb8??: the pass line's recapture a8xd8 is no longer legal, but the
# rook on b8 recaptures instead and the mate still works.
BACK = "r5k1/5ppp/8/8/8/8/3R1PPP/3R2K1 b - - 0 1"
M2 = {"mate": 2, "mate_sign": 1}


def back_scripts(**changes):
    s = {
        BACK: [L("h7h6", 0), L("g7g6", -10), L("f7f6", -20)],
        passed(BACK): [L("d2d8", pv=("d2d8", "a8d8", "d1d8"), **M2)],
        after(BACK, "a8b8"): [L("d2d8", pv=("d2d8", "b8d8", "d1d8"), **M2)],
        after(BACK, "h7h6"): [L("d2d8", 0, pv=("d2d8", "a8d8", "d1d8", "g8h7"))],
        forced(BACK, "a8b8", "d2d8"): [L("b8d8", pv=("b8d8", "d1d8"), **M2)],
    }
    s.update(changes)
    return s


def test_a_move_that_changes_the_recapture_but_not_the_mate_is_missed():
    assert TK.line_result(chess.Board(after(BACK, "a8b8")), ("d2d8", "a8d8", "d1d8"), chess.WHITE).plies == 1  # replay breaks
    f = MT.detect(chess.Board(BACK), mv("a8b8"), 30, FakeAnalyser(back_scripts()))
    assert (f.outcome, f.reason) == ("missed", "all_checks_hold")
    assert f.evidence["threat_after_move"] == "works" and f.evidence["threat_kind"] == "mate"


def test_making_luft_stops_the_back_rank_mate():
    f = MT.detect(chess.Board(BACK), mv("h7h6"), 30, FakeAnalyser(back_scripts()))
    assert (f.outcome, f.reason) == ("met", "defended")
    assert f.evidence["threat_after_move"] == "stopped"  # the engine plays the threat move and it wins nothing


def test_a_broken_replay_with_another_engine_line_is_uncertain_not_defended():
    # After ...Rb8 the engine (scripted) prefers a different first move, so nothing confirms or refutes the threat.
    scripts = back_scripts(**{after(BACK, "a8b8"): [L("d1d7", 400, pv=("d1d7", "b8b1"))]})
    f = MT.detect(chess.Board(BACK), mv("a8b8"), 30, FakeAnalyser(scripts))
    assert (f.outcome, f.reason) == ("uncertain", "threat_line_diverged")


def test_threat_after_move_order_of_rules():
    after_rb8 = chess.Board(after(BACK, "a8b8"))
    pv = ("d2d8", "a8d8", "d1d8")
    assert MT.threat_after_move(after_rb8, pv, L("d2d8", pv=("d2d8", "b8d8", "d1d8"), **M2), chess.WHITE) == "works"
    assert MT.threat_after_move(after_rb8, pv, L("d2d8", 0, pv=("d2d8",)), chess.WHITE) == "stopped"
    assert MT.threat_after_move(after_rb8, pv, L("g1f1", 0), chess.WHITE) == "diverged"
    assert MT.threat_after_move(after_rb8, ("d2e8",), L("g1f1", 0), chess.WHITE) == "stopped"  # threat move not legal


# --- SCHOLAR: an early mate threat (ply 4 start) ---------------------------------------------------------------------

SCHOLAR = play("e4", "e5", "Qh5", "Nc6", "Bc4").fen()
SCHOLAR_PREV = play("e4", "e5", "Qh5", "Nc6").fen()
MATE = {"mate": 1, "mate_sign": 1}


def scholar_scripts():
    return {
        SCHOLAR: [L("g7g6", 0), L("d8e7", -20), L("d8f6", -30)],
        passed(SCHOLAR): [L("h5f7", pv=("h5f7",), **MATE)],
        after(SCHOLAR, "g8f6"): [L("h5f7", pv=("h5f7",), **MATE)],
        after(SCHOLAR, "g7g6"): [L("h5f3", 0)],
    }


def test_scholars_mate_is_counted_from_ply_4():
    f = MT.detect(chess.Board(SCHOLAR), mv("g8f6"), 5, FakeAnalyser(scholar_scripts()), chess.Board(SCHOLAR_PREV))
    assert (f.outcome, f.reason) == ("missed", "all_checks_hold")
    e = f.evidence
    assert (e["threat_kind"], e["threat_origin"], e["threat_mates"]) == ("mate", "new", True)
    assert e["opponent_last_move"]["san"] == "Bc4"  # the bishop made the mate work, the queen delivers it
    assert e["threat_move"]["san"] == "Qxf7#"
    assert e["target_squares"] == ["f7", "e8"]
    assert e["eval_loss"] == R.MATE_CP  # a mate counts as MATE_CP from a level position


def test_blocking_with_g6_meets_the_mate_threat():
    f = MT.detect(chess.Board(SCHOLAR), mv("g7g6"), 5, FakeAnalyser(scholar_scripts()), chess.Board(SCHOLAR_PREV))
    assert (f.outcome, f.reason) == ("met", "defended")


def test_moves_before_ply_4_are_skipped_without_the_engine():
    a = FakeAnalyser({})
    f = MT.detect(chess.Board(SCHOLAR), mv("g8f6"), 3, a)
    assert (f.outcome, f.reason) == ("skipped", "before_min_ply") and a.calls == 0


# --- KNIGHT: a knight lost for a pawn (material rule 2) ----------------------------------------------------------------

KNIGHT = play("e4", "Nc6", "Nf3", "Nf6", "e5").fen()


def test_losing_a_knight_for_a_pawn_is_a_missed_threat():
    scripts = {
        KNIGHT: [L("f6d5", 0), L("f6g4", 10), L("f6e4", 40)],
        passed(KNIGHT): [L("e5f6", 250, pv=("e5f6", "e7f6"))],
        after(KNIGHT, "d7d6"): [L("e5f6", 230, pv=("e5f6", "e7f6"))],
        forced(KNIGHT, "d7d6", "e5f6"): [L("e7f6", 220, pv=("e7f6",))],
    }
    f = MT.detect(chess.Board(KNIGHT), mv("d7d6"), 5, FakeAnalyser(scripts))
    assert (f.outcome, f.reason) == ("missed", "all_checks_hold")
    assert f.evidence["threat_material"] == 2  # knight 3 minus the pawn taken back
    assert f.evidence["threat_kind"] == "capture" and f.evidence["target_squares"] == ["f6"]


def test_the_same_loss_is_no_threat_under_the_m1_material_rule():
    assert not TK.line_result(MT.passed_position(chess.Board(KNIGHT)), ("e5f6", "e7f6"), chess.WHITE, R.MATERIAL_MIN).wins
    assert TK.line_result(MT.passed_position(chess.Board(KNIGHT)), ("e5f6", "e7f6"), chess.WHITE).wins


# --- gates --------------------------------------------------------------------------------------------------------------

def test_in_check_is_skipped_without_the_engine():
    board = play("e4", "f5", "Qh5")  # 2.Qh5+, Black in check
    a = FakeAnalyser({})
    f = MT.detect(board, mv("g7g6"), 4, a)
    assert (f.outcome, f.reason) == ("skipped", "in_check") and a.calls == 0


def test_only_legal_move_and_decided_positions_are_skipped():
    only = chess.Board("7k/5Q2/8/p7/8/8/8/K7 b - - 0 1")  # the king is boxed in; ...a4 is Black's only move
    assert not only.is_check() and [m.uci() for m in only.legal_moves] == ["a5a4"]
    f = MT.detect(only, mv("a5a4"), 40, FakeAnalyser({only.fen(): [L("a5a4", 500)]}))
    assert (f.outcome, f.reason) == ("skipped", "only_legal_move")
    f = ruy("e1g1", ruy_scripts(**{RUY: [L("a4b3", 700)]}))
    assert (f.outcome, f.reason) == ("skipped", "decided")


def test_illegal_move_is_refused():
    with pytest.raises(ValueError):
        ruy("e1e3")


# --- labels: kind --------------------------------------------------------------------------------------------------------

def test_kind_fork_when_one_move_hits_the_king_and_a_rook():
    passed_board = chess.Board("4k3/8/8/8/3n4/8/8/R3K3 b - - 0 1")  # ...Nc2+ hits e1 and a1
    assert TK.kind(passed_board, ("d4c2",), mates=False) == "fork"


def test_kind_fork_when_a_pawn_grab_hits_the_queen_and_rook():
    # Fried Liver: 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.Ng5. Nxf7 takes only a pawn; what it threatens is the fork of d8 and h8.
    fried = play("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5")
    assert TK.kind(MT.passed_position(fried), ("g5f7",), mates=False) == "fork"


def test_kind_discovered_when_a_move_opens_a_line_onto_the_queen():
    passed_board = chess.Board("4r1k1/8/8/8/4n3/8/8/4Q1K1 b - - 0 1")  # ...Nd6 opens the e-file onto the queen
    assert TK.kind(passed_board, ("e4d6",), mates=False) == "discovered"


def test_kind_capture_beats_fork_and_mate_beats_everything():
    passed_board = chess.Board(passed(RUY))
    assert TK.kind(passed_board, ("b5a4",), mates=False) == "capture"
    assert TK.kind(passed_board, ("b5a4",), mates=True) == "mate"


def test_kind_other_for_a_quiet_move_or_a_broken_line():
    passed_board = chess.Board(passed(RUY))
    assert TK.kind(passed_board, ("g8f6",), mates=False) == "other"
    assert TK.kind(passed_board, ("e1g1",), mates=False) == "other"  # not legal for the side to move
    assert TK.kind(passed_board, (), mates=False) == "other"


# --- labels: the line replay ---------------------------------------------------------------------------------------------

def test_line_result_stops_at_an_illegal_move_and_finds_mate():
    board = chess.Board(passed(RUY))
    assert TK.line_result(board, ("e1g1",), chess.BLACK) == TK.LineResult(False, False, 0, 0)
    mate = TK.line_result(MT.passed_position(chess.Board(SCHOLAR)), ("h5f7",), chess.WHITE)
    assert (mate.wins, mate.mates, mate.plies) == (True, True, 1)


def test_engine_mate_counts_only_within_two_moves_for_the_right_side():
    assert MT.engine_mates(L("h5f7", mate=2, mate_sign=1), chess.WHITE)
    assert not MT.engine_mates(L("h5f7", mate=3, mate_sign=1), chess.WHITE)
    assert not MT.engine_mates(L("h5f7", mate=1, mate_sign=-1), chess.WHITE)
    assert not MT.engine_mates(L("h5f7", cp=300), chess.WHITE)


def test_passed_position_flips_the_side_and_clears_en_passant():
    board = play("e4", "d5", "e5", "f5")  # en passant on f6 is possible
    p = MT.passed_position(board)
    assert p.turn == chess.BLACK and p.ep_square is None and p.board_fen() == board.board_fen()


# --- real engine, shallow ------------------------------------------------------------------------------------------------

@pytest.mark.skipif(not (os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")), reason="Stockfish not installed")
def test_real_engine_finds_the_ruy_and_scholar_misses():
    from app.engine.stockfish import Engine

    with Engine() as engine:
        cfg = EngineConfig(engine.name, "test", "test", depth=12, multipv=3, hash_mb=16, threads=1)
        analyser = EvidenceAnalyser(engine, cfg, connect(":memory:"))
        f = MT.detect(chess.Board(RUY), mv("e1g1"), RUY_PLY, analyser, chess.Board(RUY_PREV))
        assert f.outcome == "missed", f
        assert f.evidence["threat_move"]["uci"] == "b5a4" and f.evidence["threat_origin"] == "new"
        assert MT.detect(chess.Board(RUY), mv("a4b3"), RUY_PLY, analyser, chess.Board(RUY_PREV)).outcome == "met"
        g = MT.detect(chess.Board(SCHOLAR), mv("g8f6"), 5, analyser, chess.Board(SCHOLAR_PREV))
        assert g.outcome == "missed" and g.evidence["threat_kind"] == "mate", g
