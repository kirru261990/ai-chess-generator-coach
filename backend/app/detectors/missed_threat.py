"""`missed_threat` v1 = mistake type M3, missed threat (ADR 0011).

In the position after the opponent's move (player to move), the player skips a turn and the evidence engine searches the passed
position: its best line is the **threat line**. The position holds a threat when that line mates or nets at least
M3_MATERIAL_MIN, and passing costs at least M3_THREAT_MIN_CP against the player's best move. The player's move is `missed` when it
loses at least M3_EVAL_LOSS_CP at the evidence depth and at the stability depth, and the threat line still works after it.

Outcomes (the rate is missed / (missed + met); the others are in neither part, AGENTS rule 5):
- missed: every check holds; `evidence` is the record
- met: `defended` (the threat line no longer works after the move), `countered` (it still works but the move loses less than
  M3_EVAL_LOSS_CP), or `defended_other_loss` (the move stops the threat but loses for another reason, often an M1 mistake)
- uncertain: `threat_unavoidable` (the best move cannot stop the threat line either), `threat_line_diverged` (the move loses
  M3_EVAL_LOSS_CP or more, the pass line breaks on a later reply, and the engine's best line does not start with the threat
  move, so we cannot tell; see `threat_after_move`) or `loss_not_stable`
- no_threat: `no_concrete_threat` or `passing_costs_little`
- skipped: `before_min_ply` (M3_MIN_PLY), `in_check`, `only_legal_move`, `decided`

Every finding that has a threat carries `evidence`, so later drills can use met positions too.
"""

from __future__ import annotations

import chess

from app.detectors import prd_rules as R
from app.detectors import threat_kind as TK
from app.detectors.hanging_own_v4 import Finding

DETECTOR = "missed_threat"
VERSION = "1"

THRESHOLDS = {
    "min_ply": R.M3_MIN_PLY,
    "material_min": R.M3_MATERIAL_MIN,
    "threat_min_cp": R.M3_THREAT_MIN_CP,
    "eval_loss_cp": R.M3_EVAL_LOSS_CP,
    "mate_max_moves": R.M3_MATE_MAX_MOVES,
    "max_refutation_plies": R.MAX_REFUTATION_PLIES,
    "decided_limit_cp": R.DECIDED_LIMIT_CP,
}


def gates(board: chess.Board, ply: int, before) -> str | None:
    """The M3 skips. Check comes before the engine: a null move is illegal in check, and check is a forced reply."""
    if ply < R.M3_MIN_PLY:
        return "before_min_ply"
    if board.is_check():
        return "in_check"
    if not R.has_choice(board):
        return "only_legal_move"
    if before.best is None or abs(R.line_score(before.best, board.turn)) > R.DECIDED_LIMIT_CP:
        return "decided"
    return None


def passed_position(board: chess.Board) -> chess.Board:
    """`board` with the side to move skipping its turn (no check: the caller has gated that)."""
    passed = board.copy(stack=False)
    passed.push(chess.Move.null())
    return chess.Board(passed.fen())


def engine_mates(line, beneficiary: chess.Color) -> bool:
    """The engine reports mate for `beneficiary` within M3_MATE_MAX_MOVES of its moves."""
    if line is None or line.mate is None:
        return False
    sign = line.mate_sign if line.mate_sign is not None else (1 if line.mate > 0 else -1)
    for_white = sign > 0
    return for_white == (beneficiary == chess.WHITE) and abs(line.mate) <= R.M3_MATE_MAX_MOVES


def threat_works(board: chess.Board, pv, beneficiary: chess.Color) -> bool:
    return TK.line_result(board, pv, beneficiary).wins


def threat_after_move(after_board: chess.Board, pv, after_best, opponent: chess.Color) -> str:
    """Does the threat still work after the player's move? `works`, `stopped` or `diverged`.

    The pass line holds the player's replies chosen for the *passed* position, so after a real move it can break on a reply
    that is no longer legal while the threat itself still stands (PR 96 review: ...Rb8 changes the recapture in
    Rd8+ Rxd8 Rxd8# but does not stop the mate). A broken replay is therefore never taken as proof of a defence:
    1. the pass line replayed as it stands wins -> works;
    2. the engine's best line in the real position starts with the threat move -> that line decides (works or stopped);
    3. the threat move itself is no longer legal -> stopped;
    4. the replay broke on a later move and the engine does not play the threat move -> diverged (we cannot tell).
    """
    replay = TK.line_result(after_board, pv, opponent)
    if replay.wins:
        return "works"
    if after_best is not None and after_best.move == pv[0]:
        engine = TK.line_result(after_board, after_best.pv, opponent)
        return "works" if engine.wins or engine_mates(after_best, opponent) else "stopped"
    if chess.Move.from_uci(pv[0]) not in after_board.legal_moves:
        return "stopped"
    if replay.plies < min(len(pv), R.MAX_REFUTATION_PLIES):
        return "diverged"
    return "stopped"


def detect(board: chess.Board, move: chess.Move, ply: int, analyser, previous: chess.Board | None = None) -> Finding:
    """Classify the player's `move` from `board` (player to move). `ply` is the move's half-move index in the game.

    `previous` is the position before the opponent's last move (opponent to move), used only for the `origin` label.
    """
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    if ply < R.M3_MIN_PLY or board.is_check():  # no engine call for these
        return Finding("skipped", "before_min_ply" if ply < R.M3_MIN_PLY else "in_check")
    mover, opponent = board.turn, not board.turn
    before = analyser.analyse(board)
    skip = gates(board, ply, before)
    if skip:
        return Finding("skipped", skip)
    eval_before = R.line_score(before.best, mover)

    # The pass test.
    passed = passed_position(board)
    threat = analyser.analyse(passed)
    t_line = threat.best
    if t_line is None:  # the opponent has no legal move after a pass: nothing to threaten
        return Finding("no_threat", "no_concrete_threat")
    pv = tuple(t_line.pv)
    replay = TK.line_result(passed, pv, opponent)
    mates = replay.mates or engine_mates(t_line, opponent)
    if not (replay.wins or mates):
        return Finding("no_threat", "no_concrete_threat")
    threat_size = eval_before - R.line_score(t_line, mover)

    best_board = board.copy(stack=False)
    best_board.push(chess.Move.from_uci(before.best.move))
    record = {
        "mistake_type": "M3",
        "fen": board.fen(),
        "ply": ply,
        "threat_move": R.move_ref(passed, pv[0]),
        "threat_line": {"uci": list(pv[: replay.plies or 1]), "san": R.sans(passed, pv[: replay.plies or 1])},
        "threat_kind": TK.kind(passed, pv, mates),
        "threat_origin": TK.origin(previous, pv),
        "threat_material": replay.swing,
        "threat_mates": mates,
        "threat_size_cp": threat_size,
        "best_move": R.move_ref(board, before.best.move),
        "eval_before": eval_before,
        "engine_config_id": analyser.config.id,
        "detector": DETECTOR,
        "detector_version": VERSION,
        "rules_version": R.RULES_VERSION,
        "m3_thresholds": dict(THRESHOLDS),
    }
    last = _last_move(previous, board)
    if last is not None:
        record["opponent_last_move"] = R.move_ref(previous, last.uci())

    if threat_size < R.M3_THREAT_MIN_CP:
        if threat_works(best_board, pv, opponent):
            return Finding("uncertain", "threat_unavoidable", record)
        return Finding("no_threat", "passing_costs_little")

    after_board = board.copy(stack=False)
    after_board.push(move)
    after = analyser.analyse(after_board)
    eval_after = R.line_score(after.best, mover) if after.best else R.terminal_score(after_board, mover)
    loss = eval_before - eval_after
    status = threat_after_move(after_board, pv, after.best, opponent)
    record.update({
        "player_move": R.move_ref(board, move.uci()),
        "eval_after": eval_after,
        "eval_loss": loss,
        "threat_after_move": status,
    })
    if loss < R.M3_EVAL_LOSS_CP:
        return Finding("met", "defended" if status == "stopped" else "countered", record)
    if status == "stopped":
        return Finding("met", "defended_other_loss", record)
    if status == "diverged":
        return Finding("uncertain", "threat_line_diverged", record)

    stab_depth = analyser.config.stability.depth
    s_before = analyser.analyse(board, depth=stab_depth)
    s_after = analyser.analyse(after_board, depth=stab_depth)
    stab_loss = R.line_score(s_before.best, mover) - (
        R.line_score(s_after.best, mover) if s_after.best else R.terminal_score(after_board, mover)
    )
    record.update({"eval_loss_stability": stab_loss, "stability_config_id": analyser.config.stability.id})
    if stab_loss < R.M3_EVAL_LOSS_CP:
        return Finding("uncertain", "loss_not_stable", record)

    record["target_squares"] = _targets(passed, pv, mover)
    alternatives = tuple(
        {**R.move_ref(board, line.move), "eval_loss": eval_before - R.line_score(line, mover)}
        for line in before.lines
        if eval_before - R.line_score(line, mover) <= R.SOUND_MAX_LOSS_CP
    )
    return Finding("missed", "all_checks_hold", record, alternatives)


def _last_move(previous: chess.Board | None, board: chess.Board) -> chess.Move | None:
    """The opponent's move that turned `previous` into `board`, found by trying each legal move (positions carry no history)."""
    if previous is None:
        return None
    for m in previous.legal_moves:
        b = previous.copy(stack=False)
        b.push(m)
        if b.board_fen() == board.board_fen() and b.turn == board.turn:
            return m
    return None


def _targets(passed: chess.Board, pv, mover: chess.Color) -> list[str]:
    """Squares of the player's pieces the threat line captures or mates on, in the position shown to the player."""
    b = passed.copy(stack=False)
    out: list[str] = []
    for uci in list(pv)[: R.MAX_REFUTATION_PLIES]:
        m = chess.Move.from_uci(uci)
        if m not in b.legal_moves:
            break
        victim = b.piece_at(m.to_square)
        if b.is_capture(m) and victim is not None and victim.color == mover:
            name = chess.square_name(m.to_square)
            if name not in out:
                out.append(name)
        b.push(m)
        if b.is_checkmate():
            king = b.king(mover)
            if king is not None:
                out.append(chess.square_name(king))
            break
    return out
