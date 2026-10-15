"""Sound move (PRD v2 §4.4): is the player's new move in a MISTAKE position good enough?

A move is sound when all of these hold:
1. it is legal (an illegal move raises; the caller validates first);
2. M1: after it, the original refutation line no longer wins MATERIAL_MIN (`refutation_still_wins` otherwise);
3. M2: it captures one of the free pieces, or it loses at most SOUND_MAX_LOSS_CP (`free_piece_not_taken` otherwise);
4. it loses at most SOUND_MAX_LOSS_CP against the best move (`eval_loss_too_large` otherwise).

Rule 4 applies to every move, captures included (ADR 0006, decision 7). Any legal move is checked on demand with the evidence
config; nothing here prefers the engine's top move. The original refutation is replayed move by move from the new position and
stops at the first move that is no longer legal; a first move that is no longer a capture wins nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from app.detectors import prd_rules as R

VERSION = "2"  # v2: rule 2 counts material net of the new move (as hanging_own v4)


@dataclass(frozen=True)
class Verdict:
    sound: bool
    eval_loss: int
    failed: tuple[str, ...]  # rule codes, empty when sound
    move: dict  # {uci, san}
    mate: str | None = None  # "allowed": the engine's best reply is a forced mate against the mover; "missed": the mover had one


def mate_flag(mover: chess.Color, before, after, loss: int) -> str | None:
    """Whether a forced mate is behind the loss. `R.MATE_CP` is a stand-in number for a mate score, never an amount to show, so
    the wording needs to know. "allowed": after the move the engine's best line is a mate against the mover. "missed": before
    the move the mover had a forced mate and the move lost more than SOUND_MAX_LOSS_CP (review on PR 73)."""
    if after is not None and after.best is not None and after.best.mate is not None and R.line_score(after.best, mover) < 0:
        return "allowed"
    if (before is not None and before.best is not None and before.best.mate is not None
            and R.line_score(before.best, mover) > 0 and loss > R.SOUND_MAX_LOSS_CP):
        return "missed"
    return None


def check_move(board: chess.Board, move: chess.Move, evidence: dict, analyser) -> Verdict:
    """Judge `move` played from `board` (the MISTAKE position, player to move) against its evidence record."""
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    if board.fen() != evidence["fen"]:
        raise ValueError("the board is not the evidence record's position")
    mover = board.turn
    ref = R.move_ref(board, move.uci())
    after_board = board.copy(stack=False)
    after_board.push(move)
    before = analyser.analyse(board)
    after = analyser.analyse(after_board)
    eval_after = R.line_score(after.best, mover) if after.best else R.terminal_score(after_board, mover)
    loss = R.line_score(before.best, mover) - eval_after

    failed = []
    if evidence["mistake_type"] == "M1":
        refutation = evidence["refutation_line"]["uci"]
        first = chess.Move.from_uci(refutation[0])
        if first in after_board.legal_moves and after_board.is_capture(first):
            swing, _ = R.line_swing(board, (move.uci(), *refutation), not mover, 1 + R.MAX_REFUTATION_PLIES)
            if swing >= R.MATERIAL_MIN:
                failed.append("refutation_still_wins")
    else:
        captures_free = board.is_capture(move) and chess.square_name(move.to_square) in evidence["target_squares"]
        if not captures_free and loss > R.SOUND_MAX_LOSS_CP:
            failed.append("free_piece_not_taken")
    if loss > R.SOUND_MAX_LOSS_CP:
        failed.append("eval_loss_too_large")
    return Verdict(not failed, loss, tuple(failed), ref, mate_flag(mover, before, after, loss))


def check_clean_move(board: chess.Board, move: chess.Move, analyser) -> Verdict:
    """A CLEAN position has no refutation or free piece, so only rules 1 and 4 apply: the move is legal and loses at most
    SOUND_MAX_LOSS_CP against the best move (ADR 0006 decision 16). Same config and scoring as `check_move`."""
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    mover = board.turn
    after_board = board.copy(stack=False)
    after_board.push(move)
    before = analyser.analyse(board)
    after = analyser.analyse(after_board)
    eval_after = R.line_score(after.best, mover) if after.best else R.terminal_score(after_board, mover)
    loss = R.line_score(before.best, mover) - eval_after
    failed = ("eval_loss_too_large",) if loss > R.SOUND_MAX_LOSS_CP else ()
    return Verdict(not failed, loss, failed, R.move_ref(board, move.uci()), mate_flag(mover, before, after, loss))


def verified_alternatives(board: chess.Board, evidence: dict, analyser) -> list[dict]:
    """The engine's top moves that pass `check_move`, with their losses. Pre-computed; other moves are judged on demand."""
    before = analyser.analyse(board)
    out = []
    for line in before.lines:
        verdict = check_move(board, chess.Move.from_uci(line.move), evidence, analyser)
        if verdict.sound:
            out.append({**verdict.move, "eval_loss": verdict.eval_loss})
    return out
