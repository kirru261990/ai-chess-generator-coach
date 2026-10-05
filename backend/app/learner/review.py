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


def _sign(mate: int, mate_sign: int | None) -> int:
    """Who mates. `mate_sign` is authoritative; the distance's sign is only a fallback, and
    is meaningless for a position that is already checkmate (distance 0)."""
    if mate_sign is not None:
        return mate_sign
    return 1 if mate > 0 else -1


def cp_equiv(cp: int | None, mate: int | None, mate_sign: int | None = None) -> int:
    """Single number for ranking. Mates clamp to +/-CLAMP; never shown as centipawns."""
    if mate is not None:
        return CLAMP * _sign(mate, mate_sign)
    return max(-CLAMP, min(CLAMP, cp or 0))


def for_mover(
    cp: int | None, mate: int | None, white_pov: bool, mate_sign: int | None = None
) -> tuple[int | None, int | None]:
    """Convert a White-perspective score to the mover's perspective (cp and mate distance).

    The distance of a checkmated position is 0 for both sides, so who won is carried by
    `mate_sign`; use `rank_for_mover` when the winner matters.
    """
    if white_pov:
        return cp, mate
    return (None if cp is None else -cp), (None if mate is None else -mate)


def rank_for_mover(position: dict, white_pov: bool) -> int:
    """Ranking value of a stored (White-perspective) position, from the mover's side."""
    mate = position.get("mate")
    if mate is not None:
        sign = _sign(mate, position.get("mate_sign"))
        return CLAMP * (sign if white_pov else -sign)
    cp = cp_equiv(position.get("cp"), None)
    return cp if white_pov else -cp


def fmt_eval(cp: int | None, mate: int | None, mate_sign: int | None = None) -> str:
    if mate is not None:
        sign = _sign(mate, mate_sign)
        if mate == 0:
            return "you deliver checkmate" if sign > 0 else "you are checkmated"
        return f"mate in {abs(mate)} for you" if sign > 0 else f"mate in {abs(mate)} against you"
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
        b = rank_for_mover(before, white)
        a = rank_for_mover(after, white)
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

    b = cp_equiv(best.score.cp, best.score.mate, best.score.mate_sign)
    a = cp_equiv(after.score.cp, after.score.mate, after.score.mate_sign)
    loss = b - a
    if loss < MIN_LOSS_CP or b <= ALREADY_LOST_CP:
        return None  # the shallow flag did not survive the deeper search

    acceptable = [
        board.san(chess.Move.from_uci(line.best_move))
        for line in lines
        if line.best_move
        and cp_equiv(line.score.cp, line.score.mate, line.score.mate_sign) >= b - ACCEPTABLE_WITHIN_CP
    ]
    flags = []
    if best.score.mate_sign == 1 and after.score.mate_sign != 1:
        flags.append("missed_mate")
    if after.score.mate_sign == -1 and best.score.mate_sign != -1:
        flags.append("allowed_mate")

    played_san = board.san(played)
    best_san = board.san(chess.Move.from_uci(best.best_move))
    takeaway = (
        f"{played_san} cost about {loss / 100:.1f} pawns of evaluation. "
        f"After {best_san} you stand at "
        f"{fmt_eval(best.score.cp, best.score.mate, best.score.mate_sign)}; "
        f"after {played_san} it is "
        f"{fmt_eval(after.score.cp, after.score.mate, after.score.mate_sign)}."
    )
    return {
        "ply": ply,
        "move_number": ply // 2 + 1,
        "fen_before": board.fen(),
        "played": {"uci": played.uci(), "san": played_san},
        "best": {"uci": best.best_move, "san": best_san},
        "acceptable_alternatives": acceptable,
        "eval_best": {
            "cp": best.score.cp, "mate": best.score.mate, "mate_sign": best.score.mate_sign,
        },
        "eval_after_played": {
            "cp": after.score.cp, "mate": after.score.mate, "mate_sign": after.score.mate_sign,
        },
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

