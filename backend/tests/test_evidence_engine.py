"""The evidence engine: pinned, recorded config, cache by (FEN, config) (PRD v2 §4.1, ADR 0006)."""

import os
import shutil

import chess
import pytest

from app.db.schema import connect
from app.engine.evidence import (
    EVIDENCE_DEPTH,
    STABILITY_DEPTH_DROP,
    EngineConfig,
    EvidenceAnalyser,
    check_pin,
    open_evidence,
)
from app.engine.stockfish import Analysis, Budget, EngineError, Score

CFG = EngineConfig("Stockfish 19", "nn-test.nnue", "sha", depth=18, multipv=3, hash_mb=64, threads=1)


class FakeEngine:
    """Counts searches and returns one fixed line from White's view."""

    name = "Stockfish 19"

    def __init__(self):
        self.calls = []

    def analyse_multi(self, board, multipv, budget, perspective=None, new_game=False):
        self.calls.append((board.fen(), multipv, budget.depth, perspective, new_game))
        move = next(iter(board.legal_moves)).uci()
        return [Analysis(move, Score(chess.WHITE, cp=25), (move,), budget.depth, self.name, budget)]


def test_config_id_changes_with_every_field():
    ids = {CFG.id}
    for changed in (
        CFG.at_depth(14),
        EngineConfig("Stockfish 20", "nn-test.nnue", "sha", 18, 3, 64, 1),
        EngineConfig("Stockfish 19", "nn-other.nnue", "sha", 18, 3, 64, 1),
        EngineConfig("Stockfish 19", "nn-test.nnue", "rebuilt", 18, 3, 64, 1),
        EngineConfig("Stockfish 19", "nn-test.nnue", "sha", 18, 1, 64, 1),
        EngineConfig("Stockfish 19", "nn-test.nnue", "sha", 18, 3, 128, 1),
        EngineConfig("Stockfish 19", "nn-test.nnue", "sha", 18, 3, 64, 2),
    ):
        ids.add(changed.id)
    assert len(ids) == 8
    assert CFG.id == EngineConfig("Stockfish 19", "nn-test.nnue", "sha", 18, 3, 64, 1).id  # stable


def test_stability_config_is_four_plies_shallower():
    assert CFG.stability.depth == CFG.depth - STABILITY_DEPTH_DROP == 14


def test_unpinned_engine_is_refused():
    with pytest.raises(EngineError) as e:
        check_pin("Stockfish 16", "nn-1a298aa575a0.nnue")
    assert e.value.code == "engine_not_pinned"
    with pytest.raises(EngineError):
        check_pin("Stockfish 19", "nn-something-else.nnue")


def test_engine_must_match_its_config():
    other = FakeEngine()
    other.name = "Stockfish 16"
    with pytest.raises(EngineError) as e:
        EvidenceAnalyser(other, CFG, connect(":memory:"))
    assert e.value.code == "engine_config_mismatch"


def test_results_are_cached_by_fen_and_config():
    conn = connect(":memory:")
    engine = FakeEngine()
    analyser = EvidenceAnalyser(engine, CFG, conn)
    board = chess.Board()

    first = analyser.analyse(board)
    again = analyser.analyse(board)
    assert first == again and len(engine.calls) == 1
    _fen, multipv, depth, perspective, new_game = engine.calls[0]
    assert (multipv, depth, perspective, new_game) == (3, 18, chess.WHITE, True)

    shallow = analyser.analyse(board, depth=CFG.stability.depth)  # a different config: searched, not reused
    assert len(engine.calls) == 2 and shallow.config_id == CFG.stability.id != first.config_id

    # A new analyser (e.g. after a restart) reads the stored result instead of searching.
    fresh = FakeEngine()
    assert EvidenceAnalyser(fresh, CFG, conn).analyse(board) == first and fresh.calls == []


def test_a_different_config_never_reads_another_configs_results():
    conn = connect(":memory:")
    EvidenceAnalyser(FakeEngine(), CFG, conn).analyse(chess.Board())
    rebuilt = EngineConfig("Stockfish 19", "nn-test.nnue", "rebuilt", 18, 3, 64, 1)
    engine = FakeEngine()
    EvidenceAnalyser(engine, rebuilt, conn).analyse(chess.Board())
    assert len(engine.calls) == 1


def test_search_never_sees_move_history():
    """Review finding (PR 61): the cache key is the FEN, so the search must not depend on the game's history."""
    conn = connect(":memory:")
    engine = FakeEngine()
    seen = []
    original = engine.analyse_multi

    def spy(board, *args, **kwargs):
        seen.append(len(board.move_stack))
        return original(board, *args, **kwargs)

    engine.analyse_multi = spy
    board = chess.Board("4k3/8/8/7q/8/8/8/4K3 w - - 0 1")
    for _ in range(2):
        for uci in ("e1f1", "e8f8", "f1e1", "f8e8"):
            board.push_uci(uci)
    EvidenceAnalyser(engine, CFG, conn).analyse(board)
    assert seen == [0]


def test_no_search_when_there_are_no_legal_moves():
    conn = connect(":memory:")
    engine = FakeEngine()
    mated = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert EvidenceAnalyser(engine, CFG, conn).analyse(mated).lines == ()
    assert engine.calls == []


def test_configs_are_recorded():
    conn = connect(":memory:")
    EvidenceAnalyser(FakeEngine(), CFG, conn)
    rows = conn.execute("SELECT id, depth, multipv, hash_mb, threads, score_perspective FROM engine_config").fetchall()
    assert {tuple(r) for r in rows} == {
        (CFG.id, 18, 3, 64, 1, "white"),
        (CFG.stability.id, 14, 3, 64, 1, "white"),
    }


_PINNED = os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")


@pytest.mark.skipif(not _PINNED, reason="Stockfish not installed")
def test_real_engine_is_pinned_and_reproducible():
    conn = connect(":memory:")
    try:
        ctx = open_evidence(conn)
        analyser = ctx.__enter__()
    except EngineError as e:
        if e.code == "engine_not_pinned":
            pytest.skip(f"installed Stockfish is not the pinned build: {e}")
        raise
    try:
        assert analyser.config.depth == EVIDENCE_DEPTH and analyser.config.multipv == 3
        assert len(analyser.config.binary_sha256) == 64
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
        shallow = analyser.config.at_depth(10)
        a = analyser.analyse(board, depth=shallow.depth)
        conn.execute("DELETE FROM engine_analysis")  # search again from scratch
        b = analyser.analyse(board, depth=shallow.depth)
        assert a == b and len(a.lines) == 3  # same position, same config, same answer
        assert analyser.engine.analyse(board, Budget(depth=1)).engine == "Stockfish 19"
    finally:
        ctx.__exit__(None, None, None)
