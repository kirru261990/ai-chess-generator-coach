"""Post-game review (T10, spec B3): up to three key moments per game.

A fast pass flags the user's biggest evaluation drops; each candidate is then
re-checked with a deeper engine search before it is shown. Every number comes
from the engine and is recorded with the engine version and budget. The
takeaway is a factual template, not an LLM claim; pattern-aware selection and
coaching language come later (detectors, coach).
"""

from __future__ import annotations

import chess

from app.engine.batch import game_id
from app.engine.stockfish import Budget, Engine

DEEP_BUDGET = Budget(depth=16)
MIN_LOSS_CP = 150  # smaller drops are not shown as key moments
ALREADY_LOST_CP = -700  # skip positions that were already lost before the move
ACCEPTABLE_WITHIN_CP = 50  # alternatives this close to the best move are fine
MAX_MOMENTS = 3
MAX_CANDIDATES = 8  # deep-checked at most this many flagged moves per game
CLAMP = 1000  # centipawn equivalent for mates, used only to rank mistakes


def cp_equiv(cp: int | None, mate: int | None) -> int:
    """Single number for ranking. Mates clamp to +/-CLAMP; never shown as centipawns."""
    if mate is not None:
        return CLAMP if mate > 0 else -CLAMP
    return max(-CLAMP, min(CLAMP, cp or 0))


def for_mover(cp: int | None, mate: int | None, white_pov: bool) -> tuple[int | None, int | None]:
    """Convert a White-perspective score to the mover's perspective."""
    if white_pov:
        return cp, mate
    return (None if cp is None else -cp), (None if mate is None else -mate)


def fmt_eval(cp: int | None, mate: int | None) -> str:
    if mate is not None:
        return f"mate in {abs(mate)} for you" if mate > 0 else f"mate in {abs(mate)} against you"
    return f"{(cp or 0) / 100:+.1f}"


def shallow_candidates(analysis: dict, user_color: str) -> list[dict]:
    """The user's moves ranked by evaluation drop, from the fast pass. Pure function."""
    white = user_color == "white"
    out = []
    for i, uci in enumerate(analysis["moves"]):
        if (i % 2 == 0) != white:
            continue  # opponent's move
        before, after = analysis["positions"][i], analysis["positions"][i + 1]
        if uci == before["best"]:
            continue
        b = cp_equiv(*for_mover(before["cp"], before["mate"], white))
        a = cp_equiv(*for_mover(after["cp"], after["mate"], white))
        if b <= ALREADY_LOST_CP:
            continue
        loss = b - a
        if loss >= MIN_LOSS_CP:
            out.append({"ply": i, "loss_cp": loss})
    out.sort(key=lambda c: (-c["loss_cp"], c["ply"]))
    return out[:MAX_CANDIDATES]


def _san_line(board: chess.Board, ucis: tuple[str, ...], limit: int = 6) -> list[str]:
    board = board.copy()
    sans = []
    for u in ucis[:limit]:
        move = chess.Move.from_uci(u)
        if move not in board.legal_moves:
            break
        sans.append(board.san(move))
        board.push(move)
    return sans


def confirm_moment(engine: Engine, analysis: dict, ply: int, user_color: str, deep: Budget):
    """Deep check of one flagged move. Returns a moment dict, or None if it does not hold up."""
    mover = chess.WHITE if user_color == "white" else chess.BLACK
    board = chess.Board(analysis["positions"][ply]["fen"])
    played = chess.Move.from_uci(analysis["moves"][ply])

    lines = engine.analyse_multi(board, 3, deep, perspective=mover)
    best = lines[0]
    if best.best_move == played.uci():
        return None
    after_board = board.copy()
    after_board.push(played)
    after = engine.analyse(after_board, deep, perspective=mover)

    b, a = cp_equiv(best.score.cp, best.score.mate), cp_equiv(after.score.cp, after.score.mate)
    loss = b - a
    if loss < MIN_LOSS_CP or b <= ALREADY_LOST_CP:
        return None  # the shallow flag did not survive the deeper search

    acceptable = [
        board.san(chess.Move.from_uci(line.best_move))
        for line in lines
        if line.best_move
        and cp_equiv(line.score.cp, line.score.mate) >= b - ACCEPTABLE_WITHIN_CP
    ]
    flags = []
    if best.score.mate is not None and best.score.mate > 0 and not (
        after.score.mate is not None and after.score.mate > 0
    ):
        flags.append("missed_mate")
    if after.score.mate is not None and after.score.mate < 0 and not (
        best.score.mate is not None and best.score.mate < 0
    ):
        flags.append("allowed_mate")

    played_san = board.san(played)
    best_san = board.san(chess.Move.from_uci(best.best_move))
    takeaway = (
        f"{played_san} cost about {loss / 100:.1f} pawns of evaluation. "
        f"After {best_san} you stand at {fmt_eval(best.score.cp, best.score.mate)}; "
        f"after {played_san} it is {fmt_eval(after.score.cp, after.score.mate)}."
    )
    return {
        "ply": ply,
        "move_number": ply // 2 + 1,
        "fen_before": board.fen(),
        "played": {"uci": played.uci(), "san": played_san},
        "best": {"uci": best.best_move, "san": best_san},
        "acceptable_alternatives": acceptable,
        "eval_best": {"cp": best.score.cp, "mate": best.score.mate},
        "eval_after_played": {"cp": after.score.cp, "mate": after.score.mate},
        "loss_cp": loss,
        "consequence_line": _san_line(after_board, after.pv),
        "flags": flags,
        "takeaway": takeaway,
        "evidence": {
            "engine": best.engine,
            "budget": {"depth": deep.depth, "movetime_ms": deep.movetime_ms},
        },
    }


def review_game(
    engine: Engine, game: dict, analysis: dict, deep: Budget = DEEP_BUDGET
) -> dict:
    """Review one synced game given its fast-pass analysis."""
    user_color = game["user_color"]
    candidates = shallow_candidates(analysis, user_color)
    moments = []
    for c in candidates:
        m = confirm_moment(engine, analysis, c["ply"], user_color, deep)
        if m:
            moments.append(m)
        if len(moments) == MAX_MOMENTS:
            break
    moments.sort(key=lambda m: m["ply"])
    user_moves = len(analysis["moves"]) // 2 + (
        len(analysis["moves"]) % 2 if user_color == "white" else 0
    )
    return {
        "game_id": game_id(game["source_id"]),
        "user_color": user_color,
        "opponent": game.get("opponent"),
        "result": game.get("user_result"),
        "time_control": game.get("time_control"),
        "user_moves": user_moves,
        "flagged_by_fast_pass": len(candidates),
        "moments": moments,
        "engine_fast_pass": {"engine": analysis["engine"], "budget": analysis["budget"]},
    }

