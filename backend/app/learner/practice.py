"""Replay My Mistakes (PRD v2 §6, Step 3): assisted practice on positions from the player's own games.

The web API (and later MCP) call these functions; neither has scoring logic of its own (PRD §11). Everything here uses the
PRACTICE pool only: a held-out position never reaches this module (SQLite refuses it, `app/db/schema.py`).

- **Locked until the baseline for the type is done** (§6.1, §7.1). Starting the first session for a type freezes the real-game
  baseline window (§8, `realgame.freeze_baseline_window`).
- **Selection (§6.1):** 5 positions, newest game first, from different games (a repeat game is allowed when there are fewer
  than 5 games, and recorded). Unseen positions first; then positions the player did not get right on their own first attempt.
  Positions the owner already saw on an evidence page (`excluded_reason`) are skipped. For M1, only positions where the piece
  was left in danger (ADR 0006 decision 14).
- **Flow per position (§6.2):** the board and the question, then the move, then feedback. Before the first answer a response
  holds the board, the side to move, the legal moves and the pieces that can be tapped, and nothing else: no best move, eval,
  line or target squares (the leak test). The answers are scored on the server when given and shown only in the feedback.
- **Hint ladder (§6.3):** H1 the opponent's last move, H2 the piece at risk (M1) or the capturable piece (M2), H3 the
  refutation line (M1) or the capturing move (M2). The server records the highest level used per attempt.
- **Attempts:** a retry is a new attempt and never counts as a first attempt. A first attempt with a sound move and no hint is
  "first-attempt correct"; with a sound move and a hint it is "assisted correct" (§6.3, §6.4).
- **Resume (§6.5):** every answer and hint is saved, so an interrupted session comes back to the same position, the same step
  and the same hint level.
"""

from __future__ import annotations

import io
import json
import sqlite3
from datetime import datetime

import chess
import chess.pgn

from app.db.schema import transaction
from app.learner import assessment as A
from app.learner import realgame
from app.learner.assessment import NO_THREAT, AssessmentError
from app.learner.seen import UNSEEN_BOARD

SIZE = 5
MIN_SIZE = 3  # fewer positions than this is not a session
ELAPSED_CAP_MS = 600_000

STAGES = ("recognition", "move", "feedback")
HINT_NAMES = {1: "the opponent's last move", 2: "the piece involved", 3: "the line"}

_PRACTICABLE = (
    "position.retired_at IS NULL AND position.pool = 'PRACTICE' AND position.excluded_reason IS NULL AND " + UNSEEN_BOARD
)


# --- starting ------------------------------------------------------------------------------------------------------------


def baseline_done(conn: sqlite3.Connection, mistake_type: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM assessment WHERE user = ? AND mistake_type = ? AND kind = 'BASELINE' AND status = 'submitted'"
        " AND superseded_at IS NULL",
        (A.user(), mistake_type),
    ).fetchone()
    return row is not None


def _first_attempt_clean(conn: sqlite3.Connection, position_id: int) -> bool:
    """The player got this board right on their own at the first attempt (sound move, no hint). It is a property of the board:
    one game and ply can be stored as an M1 row and an M2 row, and an attempt on either counts (review on PR 72)."""
    row = conn.execute(
        "SELECT a.move_sound, a.hint_level FROM practice_attempt a JOIN position p ON p.id = a.position_id"
        " JOIN position q ON q.game_id = p.game_id AND q.ply = p.ply"
        " WHERE q.id = ? AND a.attempt_number = 1 AND a.move IS NOT NULL ORDER BY a.id LIMIT 1",
        (position_id,),
    ).fetchone()
    return bool(row and row["move_sound"] == 1 and row["hint_level"] == 0)


def _candidates(conn: sqlite3.Connection, mistake_type: str) -> list[sqlite3.Row]:
    """Practice positions that can be chosen, newest game first: unseen ones, then practised ones not got right on their own."""
    rows = conn.execute(
        "SELECT position.id, position.game_id, position.exposure_status, g.played_at FROM position"
        " JOIN game g ON g.id = position.game_id WHERE " + _PRACTICABLE + A._TYPE_FILTER[mistake_type]
        + " ORDER BY g.played_at DESC, position.ply DESC, position.id",
    ).fetchall()
    fresh = [r for r in rows if r["exposure_status"] == "UNSEEN"]
    again = [r for r in rows if r["exposure_status"] == "PRACTICED" and not _first_attempt_clean(conn, r["id"])]
    return fresh + again


def available(conn: sqlite3.Connection, mistake_type: str) -> dict:
    cands = _candidates(conn, mistake_type)
    return {"unseen": sum(1 for r in cands if r["exposure_status"] == "UNSEEN"),
            "to_repeat": sum(1 for r in cands if r["exposure_status"] != "UNSEEN")}


def _choose(cands: list[sqlite3.Row]) -> tuple[list[sqlite3.Row], bool]:
    """Up to SIZE positions from different games, unseen first; a repeat game only when there are not enough games."""
    chosen, games = [], set()
    for r in cands:
        if len(chosen) < SIZE and r["game_id"] not in games:
            chosen.append(r)
            games.add(r["game_id"])
    repeat = False
    ids = {r["id"] for r in chosen}
    for r in cands:
        if len(chosen) < SIZE and r["id"] not in ids:
            chosen.append(r)
            ids.add(r["id"])
            repeat = True
    return chosen, repeat


def _open_session(conn: sqlite3.Connection, mistake_type: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM practice_session WHERE user = ? AND mistake_type = ? AND status IN ('created', 'in_progress')",
        (A.user(), mistake_type),
    ).fetchone()


def start_session(conn: sqlite3.Connection, mistake_type: str, *, now: datetime | None = None) -> dict:
    """Start a session for a type, or return the open one (it resumes). Locked until the baseline for the type is done.

    The look-up of an open session, the choice of positions, the freezing of the real-game window and the insert are one
    transaction: two simultaneous requests are serialised, and the second gets the first one's session (review on PR 72)."""
    A._check_type(mistake_type)
    now = A._now(now)
    with transaction(conn):
        open_ = _open_session(conn, mistake_type)
        if open_:
            return {"session_id": open_["id"], "resumed": True}
        if not baseline_done(conn, mistake_type):
            raise AssessmentError("baseline_needed", "Take the starting test for this mistake type first.")
        chosen, repeat = _choose(_candidates(conn, mistake_type))
        if len(chosen) < MIN_SIZE:
            raise AssessmentError(
                "not_enough_practice_positions",
                f"Not enough practice positions left for this mistake type ({len(chosen)} of {MIN_SIZE} needed).",
            )
        realgame.freeze_in_transaction(conn, mistake_type, now=now)  # once per type; later sessions find it frozen
        sid = conn.execute(
            "INSERT INTO practice_session (user, mistake_type, status, started_at, repeat_games) VALUES (?, ?, 'created', ?, ?)",
            (A.user(), mistake_type, A._iso(now), int(repeat)),
        ).lastrowid
        for ord_, r in enumerate(chosen):
            conn.execute(
                "INSERT INTO practice_session_position (session_id, position_id, ord) VALUES (?, ?, ?)", (sid, r["id"], ord_)
            )
    return {"session_id": sid, "resumed": False}


# --- state ---------------------------------------------------------------------------------------------------------------


def _session(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    s = conn.execute("SELECT * FROM practice_session WHERE id = ? AND user = ?", (session_id, A.user())).fetchone()
    if s is None:
        raise AssessmentError("not_found", "no such practice session")
    return s


def _positions(conn: sqlite3.Connection, session_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT sp.ord, sp.position_id, sp.done_at, p.fen, p.ply, p.mistake_type, p.evidence_json, p.engine_config_id,"
        " p.verified_alternatives_json, p.game_id FROM practice_session_position sp"
        " JOIN position p ON p.id = sp.position_id WHERE sp.session_id = ? ORDER BY sp.ord",
        (session_id,),
    ).fetchall()


def _attempts(conn: sqlite3.Connection, session_id: int, position_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM practice_attempt WHERE session_id = ? AND position_id = ? ORDER BY attempt_number",
        (session_id, position_id),
    ).fetchall()


def _stage(attempt: sqlite3.Row) -> str:
    if attempt["move"] is not None:
        return "feedback"
    return "move" if attempt["recognition_response"] is not None else "recognition"


def _current(conn: sqlite3.Connection, s: sqlite3.Row, now: datetime) -> tuple[sqlite3.Row | None, sqlite3.Row | None]:
    """The position the player is on (the first not done) and its latest attempt. The first attempt is created when the board
    is first shown: inside the write lock, after checking again, so two simultaneous first views make one attempt (review on
    PR 72). The board is marked PRACTICED for every practice row of that game and ply (an M1 and an M2 row can share it)."""
    for pos in _positions(conn, s["id"]):
        if pos["done_at"] is not None:
            continue
        attempts = _attempts(conn, s["id"], pos["position_id"])
        if not attempts:
            with transaction(conn):
                if not _attempts(conn, s["id"], pos["position_id"]):  # nobody else created it while we waited for the lock
                    conn.execute(
                        "INSERT INTO practice_attempt (session_id, position_id, attempt_number, hint_level, created_at)"
                        " VALUES (?, ?, 1, 0, ?)",
                        (s["id"], pos["position_id"], A._iso(now)),
                    )
                    conn.execute(
                        "UPDATE position SET exposure_status = 'PRACTICED' WHERE exposure_status = 'UNSEEN' AND pool = 'PRACTICE'"
                        " AND (id = ? OR (game_id, ply) IN (SELECT game_id, ply FROM position WHERE id = ?"
                        " AND game_id IS NOT NULL))",
                        (pos["position_id"], pos["position_id"]),
                    )
                conn.execute("UPDATE practice_session SET status = 'in_progress' WHERE id = ? AND status = 'created'", (s["id"],))
            attempts = _attempts(conn, s["id"], pos["position_id"])
        return pos, attempts[-1]
    return None, None


def _last_move(conn: sqlite3.Connection, pos: sqlite3.Row) -> tuple[str, str] | None:
    """(SAN, UCI) of the opponent's move that led to the position, from the game's moves (PGN text is untrusted data: only the
    moves are read, and the result is checked against the stored board)."""
    row = conn.execute("SELECT pgn FROM game WHERE id = ?", (pos["game_id"],)).fetchone()
    if row is None or pos["ply"] is None or pos["ply"] < 1:
        return None
    try:
        game = chess.pgn.read_game(io.StringIO(row["pgn"]))
        moves = list(game.mainline_moves()) if game else []
        if pos["ply"] > len(moves):
            return None
        board = game.board()
        for m in moves[: pos["ply"] - 1]:
            board.push(m)
        last = moves[pos["ply"] - 1]
        san = board.san(last)
        board.push(last)
    except (ValueError, AssertionError, AttributeError):
        return None
    if board.board_fen() != chess.Board(pos["fen"]).board_fen():
        return None
    return san, last.uci()


def _piece_words(board: chess.Board, squares: list[str]) -> str:
    return " or ".join(A._piece_words(board, sq) for sq in squares)


def hint_content(conn: sqlite3.Connection, pos: sqlite3.Row, level: int) -> dict:
    """The hint for one rung of the ladder (PRD §6.3)."""
    ev = json.loads(pos["evidence_json"])
    board = chess.Board(pos["fen"])
    if level == 1:
        last = _last_move(conn, pos)
        if last is None:
            return {"level": 1, "kind": "last_move", "text": "No last move is available for this position."}
        san, uci = last
        return {"level": 1, "kind": "last_move", "squares": [uci[:2], uci[2:4]],
                "text": f"The other side just played {san}. What does it change?"}
    if level == 2:
        squares = list(ev["target_squares"])
        who = "your" if pos["mistake_type"] == "M1" else "their"
        verb = "can be won" if pos["mistake_type"] == "M1" else "can be won for free"
        return {"level": 2, "kind": "piece", "squares": squares,
                "text": f"Look at {who} {_piece_words(board, squares)}: it {verb}."}
    line = ev["refutation_line"]
    if pos["mistake_type"] == "M1":
        text = ("If it is left there, they can play " + line["san"][0] + ". Find a move that deals with it.")
    else:
        text = "The free capture is " + line["san"][0] + "."
    return {"level": 3, "kind": "line", "uci": line["uci"][:1], "san": line["san"][:1], "text": text}


def _feedback(conn: sqlite3.Connection, pos: sqlite3.Row, attempt: sqlite3.Row) -> dict:
    """What the player may see after the move: the original mistake, the verdict, what it allowed, whether the new move avoids
    it. Built from the evidence record and the stored verdict only (PRD §12)."""
    ev = json.loads(pos["evidence_json"])
    verdict = json.loads(attempt["verdict_json"])
    sound_ = bool(attempt["move_sound"])
    line = ev["refutation_line"]
    game_move = ev["player_move"]
    if pos["mistake_type"] == "M1":
        board_line = [game_move["uci"], *line["uci"]]  # your move in the game, then what it allowed
        allowed = (f"In the game you played {game_move['san']}. That allowed {line['san'][0]}, which wins "
                   f"{ev['material_swing']} points of material. One line the engine found (not the only one): "
                   f"{' '.join(line['san'])}.")
    else:
        board_line = list(line["uci"])
        allowed = (f"In the game you played {game_move['san']}. You could have won material with {line['san'][0]} "
                   f"(worth {ev['material_swing']} points). One line the engine found (not the only one): "
                   f"{' '.join(line['san'])}.")
    alternatives = json.loads(pos["verified_alternatives_json"] or "[]")
    return {
        "original": A.explain("MISTAKE", ev, pos["fen"]),
        "game_move": game_move,
        "allowed": allowed,
        "board_line": board_line,
        "target_squares": ev["target_squares"],
        "your_tap": attempt["recognition_response"],
        "tap_correct": bool(attempt["recognition_correct"]),
        "your_move": verdict["move"],
        "sound": sound_,
        "verdict": "SOUND" if sound_ else "NOT SOUND",
        "avoids": A.move_reason(verdict, sound_, pos["mistake_type"]),
        "good_moves": [{"uci": m["uci"], "san": m["san"]} for m in alternatives],
        "hint_level": attempt["hint_level"],
    }


def get_session(conn: sqlite3.Connection, session_id: int, *, now: datetime | None = None) -> dict:
    """The session as the player may see it now. Only the current position is described, and its answers (target squares, the
    line, the verdict) only once the move is in."""
    now = A._now(now)
    s = _session(conn, session_id)
    positions = _positions(conn, session_id)
    view = {
        "session_id": s["id"], "mistake_type": s["mistake_type"], "label": A.LABELS[s["mistake_type"]], "status": s["status"],
        "total": len(positions), "done": sum(1 for p in positions if p["done_at"]), "repeat_games": bool(s["repeat_games"]),
        "current": None,
    }
    if s["status"] == "completed":
        return view
    pos, attempt = _current(conn, s, now)
    if pos is None:  # every position is done
        _complete(conn, s, now)
        view["status"] = "completed"
        return view
    if s["status"] == "created":
        view["status"] = "in_progress"
    board = chess.Board(pos["fen"])
    stage = _stage(attempt)
    cur = {
        "ord": pos["ord"], "number": view["done"] + 1, "fen": pos["fen"],
        "side_to_move": "white" if board.turn == chess.WHITE else "black",
        "legal_moves": sorted(m.uci() for m in board.legal_moves),
        "tap_squares": A.tap_squares(board, s["mistake_type"]),
        "attempt": attempt["attempt_number"], "stage": stage,
        "your_tap": attempt["recognition_response"],
        "hint_level": attempt["hint_level"],
        "hints": [hint_content(conn, pos, lv) for lv in range(1, attempt["hint_level"] + 1)],
        "feedback": _feedback(conn, pos, attempt) if stage == "feedback" else None,
    }
    view["current"] = cur
    return view


def _complete(conn: sqlite3.Connection, s: sqlite3.Row, now: datetime) -> None:
    conn.execute("UPDATE practice_session SET status = 'completed', completed_at = ? WHERE id = ? AND status <> 'completed'",
                 (A._iso(now), s["id"]))


def _on(conn: sqlite3.Connection, session_id: int, ord_: int, stage: str | tuple[str, ...], now: datetime):
    """The session, current position and attempt, checking the player is on position `ord_` at the given step."""
    s = _session(conn, session_id)
    if s["status"] == "completed":
        raise AssessmentError("session_completed", "this session is finished")
    pos, attempt = _current(conn, s, now)
    if pos is None or pos["ord"] != ord_:
        raise AssessmentError("not_current_position", "answer the position on the board")
    stages = (stage,) if isinstance(stage, str) else stage
    if _stage(attempt) not in stages:
        raise AssessmentError("wrong_step", f"this position is at the {_stage(attempt)} step")
    return s, pos, attempt


# --- the steps -----------------------------------------------------------------------------------------------------------


def submit_recognition(conn: sqlite3.Connection, session_id: int, ord_: int, tap: str, *, now: datetime | None = None) -> dict:
    """Save the answer to the question (a tap, or "none"); nothing about whether it was right is returned yet."""
    now = A._now(now)
    s, pos, attempt = _on(conn, session_id, ord_, "recognition", now)
    board = chess.Board(pos["fen"])
    if tap != NO_THREAT and tap not in A.tap_squares(board, s["mistake_type"]):
        raise AssessmentError("tap_a_piece", "tap one of " + ("your" if s["mistake_type"] == "M1" else "their")
                              + " pieces, or choose \"No immediate threat\"")
    ev = json.loads(pos["evidence_json"])
    correct = int(A.recognition_correct("MISTAKE", ev, tap))  # in practice "none" is never right (§6.2)
    conn.execute("UPDATE practice_attempt SET recognition_response = ?, recognition_correct = ? WHERE id = ?",
                 (tap, correct, attempt["id"]))
    return get_session(conn, session_id, now=now)


def submit_move(conn: sqlite3.Connection, session_id: int, ord_: int, move_uci: str, analyser, *,
                now: datetime | None = None) -> dict:
    """Judge the move with the sound-move rules (any legal move, not only the engine's choice) and show the feedback."""
    now = A._now(now)
    _, pos, attempt = _on(conn, session_id, ord_, "move", now)
    board = chess.Board(pos["fen"])
    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError:
        move = None
    if move is None or move not in board.legal_moves:
        raise AssessmentError("illegal_move", "that move is not legal here")
    ev = json.loads(pos["evidence_json"])
    ev.setdefault("engine_config_id", pos["engine_config_id"])
    verdict = A.judge(board, move, "MISTAKE", ev, analyser)
    elapsed = min(ELAPSED_CAP_MS, max(0, int((now - datetime.fromisoformat(attempt["created_at"])).total_seconds() * 1000)))
    conn.execute(
        "UPDATE practice_attempt SET move = ?, move_sound = ?, elapsed_ms = ?, verdict_json = ? WHERE id = ?",
        (move.uci(), int(verdict.sound), elapsed,
         json.dumps({"eval_loss": verdict.eval_loss, "failed": list(verdict.failed), "move": verdict.move}), attempt["id"]),
    )
    return get_session(conn, session_id, now=now)


def hint(conn: sqlite3.Connection, session_id: int, ord_: int, *, now: datetime | None = None) -> dict:
    """The next rung of the ladder (at most 3). The highest level used is saved on the attempt."""
    now = A._now(now)
    _, _, attempt = _on(conn, session_id, ord_, ("recognition", "move"), now)
    if attempt["hint_level"] < 3:
        conn.execute("UPDATE practice_attempt SET hint_level = hint_level + 1 WHERE id = ?", (attempt["id"],))
    return get_session(conn, session_id, now=now)


def retry(conn: sqlite3.Connection, session_id: int, ord_: int, *, now: datetime | None = None) -> dict:
    """Try the position again: a new attempt, never counted as a first attempt."""
    now = A._now(now)
    _, pos, attempt = _on(conn, session_id, ord_, "feedback", now)
    conn.execute(
        "INSERT INTO practice_attempt (session_id, position_id, attempt_number, hint_level, created_at) VALUES (?, ?, ?, 0, ?)",
        (session_id, pos["position_id"], attempt["attempt_number"] + 1, A._iso(now)),
    )
    return get_session(conn, session_id, now=now)


def next_position(conn: sqlite3.Connection, session_id: int, ord_: int, *, now: datetime | None = None) -> dict:
    """Finish this position and go to the next; the last one completes the session."""
    now = A._now(now)
    s, pos, _ = _on(conn, session_id, ord_, "feedback", now)
    with transaction(conn):
        conn.execute("UPDATE practice_session_position SET done_at = ? WHERE session_id = ? AND position_id = ?",
                     (A._iso(now), session_id, pos["position_id"]))
        if all(p["done_at"] or p["position_id"] == pos["position_id"] for p in _positions(conn, session_id)):
            _complete(conn, s, now)
    return get_session(conn, session_id, now=now)


# --- summary -------------------------------------------------------------------------------------------------------------


def summary(conn: sqlite3.Connection, session_id: int) -> dict:
    """PRD §6.4, after the last position. Assisted results are labelled and never mixed into anything unassisted."""
    s = _session(conn, session_id)
    if s["status"] != "completed":
        raise AssessmentError("not_finished", "the summary is shown when the session is finished")
    items = []
    for pos in _positions(conn, session_id):
        attempts = _attempts(conn, session_id, pos["position_id"])
        first = attempts[0]
        ev = json.loads(pos["evidence_json"])
        items.append({
            "number": pos["ord"] + 1, "fen": pos["fen"],
            "side_to_move": "white" if chess.Board(pos["fen"]).turn == chess.WHITE else "black",
            "attempts": len(attempts),
            "first_attempt_correct": bool(first["move_sound"] == 1 and first["hint_level"] == 0),
            "assisted_correct": bool(first["move_sound"] == 1 and first["hint_level"] > 0),
            "needed_retry": len(attempts) > 1,
            "recognized": bool(first["recognition_correct"] == 1 and first["hint_level"] == 0),
            "hint_level": max(a["hint_level"] for a in attempts),
            "original": A.explain("MISTAKE", ev, pos["fen"]),
            "target_squares": ev["target_squares"],
            "seconds": None if first["elapsed_ms"] is None else round(first["elapsed_ms"] / 1000),
        })
    return {
        "session_id": s["id"], "mistake_type": s["mistake_type"], "label": A.LABELS[s["mistake_type"]],
        "assisted": True,  # practice is always assisted (AGENTS rule 4)
        "completed": len(items), "total": len(items),
        "first_attempt_correct": sum(i["first_attempt_correct"] for i in items),
        "assisted_correct": sum(i["assisted_correct"] for i in items),
        "needed_retry": sum(i["needed_retry"] for i in items),
        "recognized": sum(i["recognized"] for i in items),
        "repeat_games": bool(s["repeat_games"]),
        "items": items,
    }


def home_status(conn: sqlite3.Connection, mistake_type: str) -> dict:
    """For the home screen: is practice unlocked, how many positions are left, and the open session if there is one."""
    open_ = _open_session(conn, mistake_type)
    session = None
    if open_:
        pos = _positions(conn, open_["id"])
        session = {"session_id": open_["id"], "done": sum(1 for p in pos if p["done_at"]), "total": len(pos)}
    last = conn.execute(
        "SELECT id FROM practice_session WHERE user = ? AND mistake_type = ? AND status = 'completed' ORDER BY id DESC LIMIT 1",
        (A.user(), mistake_type),
    ).fetchone()
    return {"unlocked": baseline_done(conn, mistake_type), "positions": available(conn, mistake_type), "session": session,
            "last_completed": last["id"] if last else None}

