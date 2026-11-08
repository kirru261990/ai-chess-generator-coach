"""First-slip finder (ADR 0020): the first big mistake a player makes in a game, with the moves the engine accepts instead.

A slip is a move at ply MIN_PLY (move 5) or later that loses at least SLIP_LOSS_CP for the mover in a position that was not already
decided (|score| under DECIDED_CP). A shallow pass (depth PREFILTER_DEPTH) nominates candidates; the evidence engine (depth 18,
MultiPV 3) confirms. Imports no LLM code. PGN text is data only.
"""

from __future__ import annotations

import hashlib
import io

import chess
import chess.pgn

from app.detectors import prd_rules as R

VERSION = "1"
BANK_VERSION = "1"  # the layout of a first-slip drill record
MIN_PLY = 8  # White's 5th move: the product evaluates from move 5 (ADR 0019 amendment)
SLIP_LOSS_CP = 150
DECIDED_CP = 600
PREFILTER_DEPTH = 10
CLEAR_MARGIN_CP = 100  # the best move must beat the second best by this much, or the position is skipped (rule 5)
ACCEPT_WITHIN_CP = 50  # a move within this of the best counts as a match


def _loss(board: chess.Board, move: chess.Move, analyser, depth: int | None):
    """(score before for the mover, loss for the mover, analysis before), or None when nothing can be searched or the game ends."""
    mover = board.turn
    before = analyser.analyse(board, depth=depth)
    nxt = board.copy(stack=False)
    nxt.push(move)
    if before.best is None or nxt.is_game_over():
        return None
    after = analyser.analyse(nxt, depth=depth)
    if after.best is None:
        return None
    start = R.line_score(before.best, mover)
    return start, start - R.line_score(after.best, mover), before


def _answers(board: chess.Board, analysis) -> tuple[list[dict], bool]:
    """(accepted moves, unclear). Accepted: lines within ACCEPT_WITHIN_CP of the best for the mover. Unclear: a line sits between
    ACCEPT_WITHIN_CP and CLEAR_MARGIN_CP worse, so it is not clear whether it counts (rule 5)."""
    mover = board.turn
    best = R.line_score(analysis.best, mover)
    accepted, unclear = [], False
    for line in analysis.lines:
        gap = best - R.line_score(line, mover)
        if gap <= ACCEPT_WITHIN_CP:
            move = chess.Move.from_uci(line.move)
            accepted.append({"uci": line.move, "san": board.san(move), "cp": R.line_score(line, mover)})
        elif gap < CLEAR_MARGIN_CP:
            unclear = True
    return accepted, unclear


def find_first_slip(pgn: str, analyser, color: chess.Color | None = None) -> dict:
    """The first slip in one game. `color` limits it to one player's moves (None: either player, for public games).

    Returns {"status": "slip", "slip": {...}}, {"status": "no_slip"}, or {"status": "unclear", "ply": n} when the first slip is
    found but it is not clear which answers count (the game then yields no drill). Raises ValueError when the PGN cannot be read.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or game.errors:
        raise ValueError("the PGN could not be read")
    board = game.board()
    for ply, node in enumerate(game.mainline()):
        move = node.move
        if ply >= MIN_PLY and (color is None or board.turn == color):
            shallow = _loss(board, move, analyser, PREFILTER_DEPTH)
            if shallow and abs(shallow[0]) < DECIDED_CP and shallow[1] >= SLIP_LOSS_CP:
                deep = _loss(board, move, analyser, None)
                if deep and abs(deep[0]) < DECIDED_CP and deep[1] >= SLIP_LOSS_CP:
                    accepted, unclear = _answers(board, deep[2])
                    # The before and after searches are independent: if the played move is also an accepted answer they disagree,
                    # so the position is not clear (rule 5). A later slip would not be the first one, so the game stops here.
                    if unclear or move.uci() in {a["uci"] for a in accepted}:
                        return {"status": "unclear", "ply": ply}
                    return {"status": "slip", "slip": {
                        "ply": ply, "fen": board.fen(), "side": "white" if board.turn else "black",
                        "played": move.uci(), "played_san": board.san(move), "loss_cp": deep[1], "accepted": accepted,
                        "versions": {"slip_finder": VERSION, "engine_config": analyser.config.id}}}
        board.push(move)
    return {"status": "no_slip"}


def to_drill(slip: dict, game_id: str, avg_rating: int | None, source: str) -> dict:
    """A bank record for one slip. `source` is "own" (the player's game) or "lichess" (a fresh drill from a public game)."""
    fen, played = slip["fen"], slip["played"]
    return {
        # the finder version is part of the id, so a rescan with a new version makes new records instead of being discarded
        "id": hashlib.sha256(f"{fen}|{played}|S1|{slip['versions']['slip_finder']}".encode()).hexdigest()[:16], "type": "S1", "source": source,
        "fen": fen, "ply": slip["ply"], "side": slip["side"], "played": played, "played_san": slip["played_san"],
        "game_id": game_id, "avg_rating": avg_rating, "accepted": [a["uci"] for a in slip["accepted"]],
        "evidence": {"loss_cp": slip["loss_cp"], "accepted": slip["accepted"]}, "versions": {**slip["versions"], "bank": BANK_VERSION},
    }
