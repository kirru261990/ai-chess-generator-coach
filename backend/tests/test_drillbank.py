"""Drill library (ADR 0017): the middlegame rule, the prefilter, and what a drill record holds. Engine results are scripted."""

import chess
import pytest

from app.detectors.hanging_own_v4 import Finding
from app.engine.evidence import EngineConfig, EvidenceAnalysis, Line
from app.learner import drillbank as DB

CFG = EngineConfig("Stockfish 19", "nn-test.nnue", "sha", depth=18, multipv=3, hash_mb=64, threads=1)

RUY = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Na5 10. Bc2 c5 11. d4 Qc7 *"


def pgn(extra_headers=""):
    return (
        '[Event "Rated Rapid game"]\n[Site "https://lichess.org/AbCd1234"]\n[WhiteElo "900"]\n[BlackElo "1100"]\n'
        + extra_headers + "\n" + RUY + "\n"
    )


class FakeAnalyser:
    """White-side centipawn scores by FEN (default 0). `depths` records the depths asked for."""

    config = CFG

    def __init__(self, scores=None):
        self.scores = scores or {}
        self.depths = []

    def analyse(self, board, depth=None):
        self.depths.append(depth)
        cp = self.scores.get(board.fen(), 0)
        move = next(iter(board.legal_moves), None)
        lines = (Line(move.uci(), (move.uci(),), cp, None, None, depth or 18),) if move else ()
        return EvidenceAnalysis(board.fen(), CFG.at_depth(depth or 18).id, lines)


class StubDetector:
    DETECTOR, VERSION = "stub", "9"

    def __init__(self, outcome="mistake"):
        self.outcome, self.calls = outcome, []

    def detect(self, board, move, ply, analyser):
        self.calls.append(ply)
        return Finding(self.outcome, "stub", {"note": "evidence"}, ({"move": "e2e4"},))


def fen_before(ply):
    b = chess.Board()
    moves = [m for m in RUY.replace("*", "").split() if not m.endswith(".")]
    for san in moves[:ply]:
        b.push_san(san)
    return b


def test_start_position_and_late_plies_are_not_middlegame():
    assert not DB.in_middlegame(chess.Board(), 0)
    assert DB.in_middlegame(fen_before(12), 12)
    assert not DB.in_middlegame(fen_before(12), 11)
    assert not DB.in_middlegame(fen_before(12), 61)


def test_too_few_pieces_is_not_middlegame():
    two_each = chess.Board("r3k2r/pp3ppp/8/8/8/8/PP3PPP/R3K2R w - - 0 30")
    assert not DB.in_middlegame(two_each, 40)
    black_short = chess.Board("rn2k2r/pp3ppp/8/8/8/8/PP3PPP/RNBQK2R w - - 0 30")  # White 4 pieces, Black 3 (r, n, r)
    assert DB.in_middlegame(black_short, 40)
    black_two = chess.Board("r3k2r/pp3ppp/8/8/8/8/PP3PPP/RNBQK2R w - - 0 30")  # Black only 2
    assert not DB.in_middlegame(black_two, 40)


def test_game_info_reads_public_id_and_average_rating():
    import io

    import chess.pgn

    g = chess.pgn.read_game(io.StringIO(pgn()))
    assert DB.game_info(g) == {"game_id": "AbCd1234", "avg_rating": 1000}


def test_drill_id_is_stable_and_depends_on_type():
    a = DB.drill_id("fen", "e2e4", "M1")
    assert a == DB.drill_id("fen", "e2e4", "M1") and a != DB.drill_id("fen", "e2e4", "M2") and len(a) == 16


def test_only_moves_losing_enough_reach_the_detector(monkeypatch):
    stub = StubDetector()
    monkeypatch.setitem(DB.DETECTORS, "M1", stub)
    b12 = fen_before(12)
    mv = b12.parse_san("Bb3")
    b13 = b12.copy()
    b13.push(mv)
    # White's ply-12 move: the score before is 0, after it is -250 for White (Black ahead), a 250 cp loss
    fa = FakeAnalyser({b13.fen(): -250})
    drills = [d for d in DB.scan_game(pgn(), fa, types=("M1",)) if d["ply"] == 12]  # ply 13 also "loses" the scripted lead back
    assert 12 in stub.calls and 11 not in stub.calls
    assert len(drills) == 1
    d = drills[0]
    assert d["type"] == "M1" and d["fen"] == b12.fen() and d["played"] == mv.uci() and d["played_san"] == "Bb3"
    assert d["side"] == "white" and d["game_id"] == "AbCd1234" and d["avg_rating"] == 1000
    assert d["evidence"] == {"note": "evidence"} and d["alternatives"] == [{"move": "e2e4"}]
    assert d["versions"]["bank"] == DB.BANK_VERSION and d["versions"]["detector"] == "stub:9"
    assert d["versions"]["engine_config"] == CFG.id and d["experimental"] is False
    assert set(fa.depths) == {DB.PREFILTER_DEPTH}  # the cheap pass only; the stub detector asked for nothing deeper


def test_small_losses_and_other_outcomes_make_no_drill(monkeypatch):
    stub = StubDetector(outcome="uncertain")
    monkeypatch.setitem(DB.DETECTORS, "M1", stub)
    b12 = fen_before(12)
    b13 = b12.copy()
    b13.push(b12.parse_san("Bb3"))
    assert DB.scan_game(pgn(), FakeAnalyser({b13.fen(): -250}), types=("M1",)) == []  # uncertain is dropped
    assert 12 in stub.calls
    stub2 = StubDetector()
    monkeypatch.setitem(DB.DETECTORS, "M1", stub2)
    assert DB.scan_game(pgn(), FakeAnalyser({b13.fen(): -50}), types=("M1",)) == []  # below the prefilter
    assert stub2.calls == []


def test_black_move_loss_is_seen_from_black(monkeypatch):
    stub = StubDetector()
    monkeypatch.setitem(DB.DETECTORS, "M1", stub)
    b13 = fen_before(13)
    after = b13.copy()
    after.push(b13.parse_san("d6"))
    drills = DB.scan_game(pgn(), FakeAnalyser({after.fen(): 300}), types=("M1",))  # +300 for White is a 300 cp loss for Black
    assert [d["side"] for d in drills if d["ply"] == 13] == ["black"] and 13 in stub.calls


def test_unreadable_pgn_raises():
    with pytest.raises(ValueError):
        DB.scan_game("1. e5 *", FakeAnalyser())


def test_m3_is_off_by_default_and_marked_experimental():
    assert "M3" not in DB.DEFAULT_TYPES


def test_each_type_keeps_the_outcome_its_detector_reports(monkeypatch):
    # M2 and M3 call a real error "missed", M1 calls it "mistake": a drill is kept only under the right word (found on the first real run)
    assert DB.DRILL_OUTCOME == {"M1": "mistake", "M2": "missed", "M3": "missed"}
    stub = StubDetector(outcome="missed")
    monkeypatch.setitem(DB.DETECTORS, "M2", stub)
    b12 = fen_before(12)
    b13 = b12.copy()
    b13.push(b12.parse_san("Bb3"))
    drills = [d for d in DB.scan_game(pgn(), FakeAnalyser({b13.fen(): -250}), types=("M2",)) if d["ply"] == 12]
    assert [d["type"] for d in drills] == ["M2"]
