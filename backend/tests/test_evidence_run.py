"""The Step 1b runner's candidate filter (the evidence engine decides; this only chooses what it sees)."""

import chess

from app.learner.evidence_run import candidates


def fast_pass(ucis, cps):
    board, positions = chess.Board(), []
    for i in range(len(ucis) + 1):
        positions.append({"ply": i, "fen": board.fen(), "cp": cps.get(i, 30), "mate": None, "mate_sign": None})
        if i < len(ucis):
            board.push_uci(ucis[i])
    return {"moves": ucis, "positions": positions}


def test_big_loss_that_leaves_a_piece_is_an_m1_candidate_and_openings_are_skipped():
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "c2c3", "g8f6", "c4f7", "e8f7"]  # ply 8: Bxf7+ Kxf7 loses the bishop
    analysis = fast_pass(moves, {9: -250, 10: -250})
    mistakes, cleans = candidates(analysis, white=True, platform_id="1")
    assert [(m["ply"], m["move"], m["types"]) for m in mistakes] == [(8, "c4f7", ["M1"])]
    assert cleans == []
    as_black, _ = candidates(analysis, white=False, platform_id="1")
    assert as_black == []  # Black's moves: ply 9 lost nothing for Black


def test_no_candidates_before_min_ply():
    moves = ["e2e4", "e7e5", "d1h5", "b8c6", "h5e5"]  # Qxe5+ at ply 4 is still the opening by the PRD's rule
    analysis = fast_pass(moves, {5: -400})
    assert candidates(analysis, white=True, platform_id="1") == ([], [])
