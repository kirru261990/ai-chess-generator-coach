import os
import shutil

import chess
import pytest

from app.coach import verifier as v
from app.engine.stockfish import Analysis, Budget, Score

FREE_KNIGHT = "4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1"  # Rd1 takes the loose knight on d5
HUNG = "4k3/8/8/3p4/4N3/8/8/4K3 w - - 0 1"  # the knight on e4 can be taken by the pawn


class FakeEngine:
    """Scores by FEN (White's view of the centipawns), best move by FEN; mover-relative like the real one."""

    def __init__(self, cp=None, best=None, mate=None):
        self.cp, self.best, self.mate = cp or {}, best or {}, mate or {}

    def analyse(self, board, budget=None, perspective=None):
        perspective = board.turn if perspective is None else perspective
        white_cp = self.cp.get(board.fen(), 0)
        sign = 1 if perspective == chess.WHITE else -1
        mate = self.mate.get(board.fen())
        score = Score(perspective, mate=mate[0], mate_sign=mate[1] * sign) if mate else Score(perspective, cp=white_cp * sign)
        return Analysis(self.best.get(board.fen()), score, (), 12, "fake", Budget(depth=12))


def ctx(fen=FREE_KNIGHT, played=None):
    return v.Context(fen, chess.WHITE, played)


def check(claim, engine=None, context=None):
    report = v.verify(engine or FakeEngine(), context or ctx(), [claim])
    return report


def ok(claim, **kw):
    r = check(claim, **kw)
    assert r.ok, r.failed
    return r


def bad(claim, **kw):
    r = check(claim, **kw)
    assert len(r.failed) == 1
    return r.failed[0]["reason"]


def test_legal_and_illegal_moves():
    ok({"type": "move_legal", "move": "Rxd5"})
    ok({"type": "move_legal", "move": "d1d5"})
    assert "not a legal move" in bad({"type": "move_legal", "move": "Rxd8"})
    assert "not a legal move" in bad({"type": "move_legal", "move": "Qh5"})


def test_a_line_must_be_playable_in_order():
    ok({"type": "line_legal", "moves": ["Rxd5", "Ke7"]})
    bad({"type": "line_legal", "moves": ["Rxd5", "Kd7"]})  # the king may not step onto the rook's file
    bad({"type": "line_legal", "moves": ["Rxd5", "Ke7", "Qh5"]})
    bad({"type": "line_legal", "moves": []})


def test_move_captures():
    ok({"type": "move_captures", "move": "Rxd5"})
    assert "does not capture" in bad({"type": "move_captures", "move": "Rd2"})


def test_best_move_uses_the_engine():
    quiet = chess.Board(FREE_KNIGHT)
    quiet.push_san("Rd2")
    eng = FakeEngine(cp={FREE_KNIGHT: 300, quiet.fen(): 0}, best={FREE_KNIGHT: "d1d5"})
    ok({"type": "best_move", "move": "Rxd5"}, engine=eng)
    assert "not the engine's choice" in bad({"type": "best_move", "move": "Rd2"}, engine=eng)


def test_best_move_accepts_an_equal_alternative():
    after_alt = chess.Board(FREE_KNIGHT)
    after_alt.push_san("Rd2")
    eng = FakeEngine(cp={FREE_KNIGHT: 300, after_alt.fen(): 290}, best={FREE_KNIGHT: "d1d5"})
    ok({"type": "best_move", "move": "Rd2"}, engine=eng)


def test_piece_can_be_taken_uses_the_detector():
    context = ctx(HUNG)
    ok({"type": "piece_can_be_taken", "square": "e4", "side": "user"}, context=context)
    assert "no piece on e4" in bad({"type": "piece_can_be_taken", "square": "e4", "side": "opponent"}, context=context)
    assert "not a square" in bad({"type": "piece_can_be_taken", "square": "z9", "side": "user"}, context=context)
    assert "side must be" in bad({"type": "piece_can_be_taken", "square": "e4"}, context=context)


def test_free_piece_available():
    ok({"type": "free_piece_available", "square": "d5"})
    assert "no free piece" in bad({"type": "free_piece_available", "square": "d1"})


def test_after_claims_use_the_position_after_the_played_move():
    context = ctx(FREE_KNIGHT, played="d1d5")
    ok({"type": "move_legal", "move": "Ke7", "position": "after"}, context=context)  # Black to move after Rxd5
    bad({"type": "move_legal", "move": "Ke7"}, context=context)  # not legal for White before
    assert "unknown position" in bad({"type": "move_legal", "move": "Ke7", "position": "later"}, context=context)


def test_after_without_a_played_move_fails():
    bad({"type": "move_legal", "move": "Ke7", "position": "after"})


def test_eval_band_is_checked_from_the_users_side():
    eng = FakeEngine(cp={FREE_KNIGHT: 300})
    ok({"type": "eval_band", "band": "winning"}, engine=eng)
    assert "not 'equal'" in bad({"type": "eval_band", "band": "equal"}, engine=eng)
    black = v.Context(FREE_KNIGHT, chess.BLACK)  # same White score is bad for a Black user
    ok({"type": "eval_band", "band": "losing"}, engine=eng, context=black)
    assert "unknown band" in bad({"type": "eval_band", "band": "great"}, engine=eng)


def test_mate_claims_need_the_engines_mate():
    eng = FakeEngine(mate={FREE_KNIGHT: (2, 1)})
    ok({"type": "mate_in", "side": "user", "moves": 3}, engine=eng)
    bad({"type": "mate_in", "side": "user", "moves": 1}, engine=eng)
    bad({"type": "mate_in", "side": "opponent", "moves": 3}, engine=eng)
    bad({"type": "mate_in", "side": "user", "moves": 3})


def test_unknown_claim_types_and_malformed_claims_fail():
    assert "unknown claim type" in bad({"type": "vibes"})
    assert "unknown claim type" in bad({})
    r = v.verify(FakeEngine(), ctx(), ["not an object"])
    assert not r.ok and "must be an object" in r.failed[0]["reason"]


def test_one_bad_claim_does_not_hide_the_good_ones():
    r = v.verify(FakeEngine(), ctx(), [{"type": "move_legal", "move": "Rxd5"}, {"type": "move_legal", "move": "Qh5"}])
    assert len(r.verified) == 1 and len(r.failed) == 1 and not r.ok


@pytest.mark.parametrize("text,problems", [
    ("Rxd5 wins the knight.", 0),
    ("Qxf7# would end it.", 1),
    ("Castle with O-O soon.", 1),
    ("Put a pawn on e4 and your king on g1.", 0),  # bare squares are not moves
    ("exd5 was possible.", 1),
])
def test_prose_may_only_name_verified_moves(text, problems):
    assert len(v.check_prose(text, {"Rxd5"}, set())) == problems


def test_prose_pawn_amounts_must_match_the_engine():
    assert v.check_prose("That cost about 3.0 pawns.", set(), {3.0}) == []
    assert len(v.check_prose("That cost about 5 pawns.", set(), {3.0})) == 1


def test_verify_checks_prose_against_the_verified_claims_and_known_moves():
    claims = [{"type": "move_legal", "move": "Rxd5"}]
    assert v.verify(FakeEngine(), ctx(), claims, "Rxd5 wins a knight.").ok
    r = v.verify(FakeEngine(), ctx(), claims, "Rxd5 wins a knight, and Rd8+ follows.")
    assert not r.ok and "Rd8+" in r.prose_problems[0]
    assert v.verify(FakeEngine(), ctx(), [], "Rd8+ was the move.", known_moves=["Rd8+"]).ok


needs_engine = pytest.mark.skipif(
    not (os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")), reason="Stockfish not installed"
)


@needs_engine
def test_with_the_real_engine_the_free_knight_claims_hold():
    from app.engine.stockfish import Engine

    with Engine() as engine:
        r = v.verify(engine, ctx(), [
            {"type": "best_move", "move": "Rxd5"},
            {"type": "free_piece_available", "square": "d5"},
            {"type": "eval_band", "band": "winning"},
        ])
        assert r.ok, r.failed
        assert not v.verify(engine, ctx(), [{"type": "best_move", "move": "Rd2"}]).ok
