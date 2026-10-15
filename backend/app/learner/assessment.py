"""Unassisted assessments (PRD v2 §7; Step 2 builds the baseline). The only code that hands out held-out positions.

The web API and, later, the MCP server call these functions; neither has scoring logic of its own (PRD §11).

- **Pool check (§5.2):** a mistake type is ready when the held-out pool still has at least MIN_HELDOUT_MISTAKE MISTAKE and
  MIN_HELDOUT_CLEAN CLEAN positions that can be assessed. Otherwise the counts are shown and nothing starts.
- **Allocation (§7.3):** 5 positions, 3 or 4 MISTAKE of the type and the rest CLEAN, from different games where possible, in
  random order. Only held-out, unseen, not retired positions whose board was never shown or assessed. For M1, only positions
  where the piece was left in danger (ADR 0006 decision 14). The database refuses anything else (`app/db/schema.py`).
- **Before the final submit (§7.4, §11)** a response holds the current board and its legal moves only: never the kind, the
  answer, the best move, an eval, a line or a verdict. Answers are scored when given and revealed only after the final submit.
- **The tap (question version 2, ADR 0006 decision 24):** M1 asks about the player's own pieces, M2 about the opponent's, and
  only those can be tapped; the server refuses any other tap. Assessments taken before v6 are version 1 (either side could be
  tapped) and keep their own random-guess rate.
- **Scoring (§7.5):** recognition is correct when the tapped square is a target square (MISTAKE) or the answer is "No
  immediate threat" (CLEAN). The move is judged with the sound-move rules (`detectors/sound.py`) at the position's own engine
  config; a different config is refused, never compared. Combined = both. Random-guess rates sit next to every score.
- **Time (§7.4):** the server times each decision from when it first showed the board, capped at 300 s. A board shown again
  after RESHOW_GAP_S (the test was left and resumed) is flagged as interrupted.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import UTC, datetime

import chess

from app import config
from app.db.schema import transaction
from app.detectors import clean, sound
from app.detectors import prd_rules as R
from app.engine.evidence import cached_analysis
from app.learner.seen import UNSEEN_BOARD

TYPES = ("M1", "M2")
SIZE = 5
MISTAKE_COUNTS = (3, 4)  # PRD §7.3: 3-4 MISTAKE and 1-2 CLEAN
MIN_HELDOUT_MISTAKE = 16  # PRD §5.2: one baseline and three delayed assessments
MIN_HELDOUT_CLEAN = 8
TIME_CAP_MS = 300_000
RESHOW_GAP_S = 10  # a page that asks for the same board twice in a row is not an interruption
NO_THREAT = "none"
QUESTION_VERSION = "2"  # the recognition wording; schema v6 records it on each assessment

LABELS = {"M1": "Pieces left in danger", "M2": "Free pieces to take"}
CUES = {
    "M1": "This test is about pieces left in danger. Each position has two steps. Step 1 is a question: tap one of YOUR "
          "pieces that the other side can win, or choose \"No immediate threat\". It is not a move yet. Step 2 is your move. "
          "There is no help and no feedback until the end.",
    "M2": "This test is about free pieces. Each position has two steps. Step 1 is a question: tap one of THEIR pieces that "
          "you can win for free, or choose \"No immediate threat\". It is not a move yet. Step 2 is your move. "
          "There is no help and no feedback until the end.",
}
# Plain words for why a "nothing is wrong" position is left out of the score (clean v2, ADR 0006 decision 27)
LEFT_OUT_WORDS = {
    "player_has_free_capture": "you could win something here, even if only a pawn",
    "player_piece_can_be_won": "something of yours could be won, even for a small gain",
    "in_check": "you were in check",
    "best_line_wins_material": "the engine's best line started by winning something",
}
V1_NOTE = ("This test used the first wording of the tap question, which let you tap a piece of either side and was easy to "
           "mix up with your move. Trust the move score. The tap score cannot be compared with later tests.")

# A held-out position that can still be assessed. Unaliased `position` (UNSEEN_BOARD refers to it).
_ASSESSABLE = (
    "position.retired_at IS NULL AND position.pool = 'HELDOUT' AND position.exposure_status = 'UNSEEN'"
    " AND position.excluded_reason IS NULL AND " + UNSEEN_BOARD +
    " AND NOT EXISTS (SELECT 1 FROM assessment_position ap JOIN position s ON s.id = ap.position_id"
    " WHERE s.game_id = position.game_id AND s.ply = position.ply)"
)
_TYPE_FILTER = {
    "M1": " AND position.kind = 'MISTAKE' AND position.mistake_type = 'M1'"
          " AND json_extract(position.evidence_json, '$.lost_piece') = 'other'",
    "M2": " AND position.kind = 'MISTAKE' AND position.mistake_type = 'M2'",
}
_CLEAN_FILTER = " AND position.kind = 'CLEAN'"


class AssessmentError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def user() -> str:
    return (config.chesscom_username() or "owner").lower()


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds")


def tap_squares(board: chess.Board, mistake_type: str, question_version: str = QUESTION_VERSION) -> list[str]:
    """The squares the player may tap at the question step: M1 their own pieces, M2 the opponent's (version 2); any piece
    in version 1."""
    if question_version == "1":
        return sorted(chess.square_name(sq) for sq in board.piece_map())
    side = board.turn if mistake_type == "M1" else not board.turn
    return sorted(chess.square_name(sq) for sq, piece in board.piece_map().items() if piece.color == side)


def _check_type(mistake_type: str) -> None:
    if mistake_type not in TYPES:
        raise AssessmentError("unknown_mistake_type", f"mistake type must be one of {', '.join(TYPES)}")


# --- pool check and home -------------------------------------------------------------------------------------------------


def _assessable(conn: sqlite3.Connection, where: str) -> list[sqlite3.Row]:
    return conn.execute(
        f"SELECT position.id, position.game_id FROM position WHERE {_ASSESSABLE}{where} ORDER BY position.id"
    ).fetchall()


def pool_status(conn: sqlite3.Connection, mistake_type: str) -> dict:
    """Counts of held-out positions that can still be assessed for this type, and whether the PRD §5.2 minimum is met."""
    _check_type(mistake_type)
    mistakes = len(_assessable(conn, _TYPE_FILTER[mistake_type]))
    cleans = len(_assessable(conn, _CLEAN_FILTER))
    return {
        "mistake_positions": mistakes,
        "clean_positions": cleans,
        "needed_mistake_positions": MIN_HELDOUT_MISTAKE,
        "needed_clean_positions": MIN_HELDOUT_CLEAN,
        "ready": mistakes >= MIN_HELDOUT_MISTAKE and cleans >= MIN_HELDOUT_CLEAN,
    }


def home(conn: sqlite3.Connection) -> dict:
    """Per mistake type: pool counts, and the baseline's status (none, open or done)."""
    out = []
    for t in TYPES:
        row = conn.execute(
            "SELECT id, status FROM assessment WHERE user = ? AND mistake_type = ? AND kind = 'BASELINE'"
            " AND superseded_at IS NULL ORDER BY id DESC LIMIT 1",
            (user(), t),
        ).fetchone()
        baseline = {"assessment_id": row["id"], "status": row["status"]} if row else None
        out.append({"mistake_type": t, "label": LABELS[t], "pool": pool_status(conn, t), "baseline": baseline})
    return {"types": out}


# --- starting a baseline -------------------------------------------------------------------------------------------------


def _pick(rows: list[sqlite3.Row], n: int, rng: random.Random, used_games: set[str]) -> list[sqlite3.Row]:
    """`n` rows in random order, from games not used yet where possible (PRD §6.1 spirit: different games)."""
    rows = list(rows)
    rng.shuffle(rows)
    picked = []
    for row in rows:
        if len(picked) < n and row["game_id"] not in used_games:
            picked.append(row)
            used_games.add(row["game_id"])
    ids = {row["id"] for row in picked}
    for row in rows:  # not enough different games: allow a repeat game rather than fail
        if len(picked) < n and row["id"] not in ids:
            picked.append(row)
            ids.add(row["id"])
    return picked


def start_baseline(conn: sqlite3.Connection, mistake_type: str, *, rng: random.Random | None = None,
                   now: datetime | None = None) -> dict:
    """Create the BASELINE assessment for a type, or return the open one (resume). One baseline per type, ever."""
    _check_type(mistake_type)
    row = conn.execute(
        "SELECT id, status FROM assessment WHERE user = ? AND mistake_type = ? AND kind = 'BASELINE'"
        " AND superseded_at IS NULL ORDER BY id DESC LIMIT 1",
        (user(), mistake_type),
    ).fetchone()
    if row and row["status"] == "submitted":
        raise AssessmentError("baseline_done", "the baseline for this mistake type is already done")
    if row:
        return {"assessment_id": row["id"], "resumed": True}
    status = pool_status(conn, mistake_type)
    if not status["ready"]:
        raise AssessmentError(
            "pool_too_small",
            "Not enough games yet for this mistake type: "
            f"{status['mistake_positions']} of {MIN_HELDOUT_MISTAKE} mistake positions and "
            f"{status['clean_positions']} of {MIN_HELDOUT_CLEAN} clean positions",
        )
    rng = rng or random.SystemRandom()
    n_mistakes = rng.choice(MISTAKE_COUNTS)
    used: set[str] = set()
    chosen = _pick(_assessable(conn, _TYPE_FILTER[mistake_type]), n_mistakes, rng, used)
    chosen += _pick(_assessable(conn, _CLEAN_FILTER), SIZE - n_mistakes, rng, used)
    rng.shuffle(chosen)
    t = _iso(_now(now))
    with transaction(conn):
        aid = conn.execute(
            "INSERT INTO assessment (user, mistake_type, kind, created_at, due_at, status, question_version)"
            " VALUES (?, ?, 'BASELINE', ?, ?, 'pending', ?)",
            (user(), mistake_type, t, t, QUESTION_VERSION),
        ).lastrowid
        for ord_, r in enumerate(chosen):
            conn.execute(
                "INSERT INTO assessment_position (assessment_id, position_id, ord) VALUES (?, ?, ?)", (aid, r["id"], ord_)
            )
    return {"assessment_id": aid, "resumed": False}


# --- taking it -----------------------------------------------------------------------------------------------------------


def _load(conn: sqlite3.Connection, assessment_id: int) -> sqlite3.Row:
    a = conn.execute("SELECT * FROM assessment WHERE id = ? AND user = ?", (assessment_id, user())).fetchone()
    if a is None:
        raise AssessmentError("not_found", "no such assessment")
    return a


def _items(conn: sqlite3.Connection, assessment_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT ap.ord, ap.position_id, p.fen, p.kind, p.evidence_json, p.engine_config_id, r.id AS result_id"
        " FROM assessment_position ap JOIN position p ON p.id = ap.position_id"
        " LEFT JOIN assessment_result r ON r.assessment_id = ap.assessment_id AND r.position_id = ap.position_id"
        " WHERE ap.assessment_id = ? ORDER BY ap.ord",
        (assessment_id,),
    ).fetchall()


def _record_view(conn: sqlite3.Connection, assessment_id: int, position_id: int, now: datetime) -> None:
    t = _iso(now)
    row = conn.execute(
        "SELECT last_shown_at FROM assessment_view WHERE assessment_id = ? AND position_id = ?", (assessment_id, position_id)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO assessment_view (assessment_id, position_id, first_shown_at, last_shown_at, shown_count)"
            " VALUES (?, ?, ?, ?, 1)",
            (assessment_id, position_id, t, t),
        )
        return
    gap = (now - datetime.fromisoformat(row["last_shown_at"])).total_seconds()
    conn.execute(
        "UPDATE assessment_view SET last_shown_at = ?, shown_count = shown_count + ? WHERE assessment_id = ? AND position_id = ?",
        (t, 1 if gap >= RESHOW_GAP_S else 0, assessment_id, position_id),
    )


def get_assessment(conn: sqlite3.Connection, assessment_id: int, *, now: datetime | None = None) -> dict:
    """The assessment as the player may see it now: the current board only, nothing about answers until it is submitted."""
    now = _now(now)
    a = _load(conn, assessment_id)
    items = _items(conn, assessment_id)
    answered = sum(1 for i in items if i["result_id"] is not None)
    current = next((i for i in items if i["result_id"] is None), None)
    view = {
        "assessment_id": a["id"],
        "assessment_kind": a["kind"],
        "mistake_type": a["mistake_type"],
        "label": LABELS[a["mistake_type"]],
        "cue": CUES[a["mistake_type"]],
        "status": a["status"],
        "total": len(items),
        "answered": answered,
        "current": None,
        "ready_to_submit": a["status"] != "submitted" and current is None,
    }
    if a["status"] == "submitted" or current is None:
        return view
    with transaction(conn):
        if a["status"] == "pending":
            conn.execute("UPDATE assessment SET status = 'in_progress' WHERE id = ?", (a["id"],))
            view["status"] = "in_progress"
        _record_view(conn, a["id"], current["position_id"], now)
    board = chess.Board(current["fen"])
    view["current"] = {
        "ord": current["ord"],
        "number": answered + 1,
        "fen": current["fen"],
        "side_to_move": "white" if board.turn == chess.WHITE else "black",
        "legal_moves": sorted(m.uci() for m in board.legal_moves),
        "tap_squares": tap_squares(board, a["mistake_type"], a["question_version"]),
    }
    return view


def judge(board: chess.Board, move: chess.Move, kind: str, evidence: dict, analyser) -> sound.Verdict:
    """The sound-move verdict for a MISTAKE or CLEAN position (same engine config as the position, or refused)."""
    if analyser.config.id != evidence["engine_config_id"]:
        raise AssessmentError(
            "engine_config_changed",
            f"this position was analysed with {evidence['engine_config_id']}; the engine here is {analyser.config.id}."
            " Results from different engine settings are never compared (PRD §4.1).",
        )
    if kind == "CLEAN":
        return sound.check_clean_move(board, move, analyser)
    return sound.check_move(board, move, evidence, analyser)


def recognition_correct(kind: str, evidence: dict, response: str) -> bool:
    if kind == "CLEAN":
        return response == NO_THREAT
    return response in evidence["target_squares"]


def submit_item(conn: sqlite3.Connection, assessment_id: int, ord_: int, recognition: str, move_uci: str, analyser,
                *, now: datetime | None = None) -> dict:
    """Record the answer for the current board (a tap or "none", and a move) and return the next board. Nothing about
    whether the answer was right is returned."""
    now = _now(now)
    a = _load(conn, assessment_id)
    if a["status"] == "submitted":
        raise AssessmentError("assessment_submitted", "this assessment is already submitted")
    current = next((i for i in _items(conn, assessment_id) if i["result_id"] is None), None)
    if current is None or current["ord"] != ord_:
        raise AssessmentError("not_current_position", "answer the position on the board; a submitted one cannot be changed")
    board = chess.Board(current["fen"])
    if recognition != NO_THREAT and recognition not in tap_squares(board, a["mistake_type"], a["question_version"]):
        raise AssessmentError(
            "tap_a_piece",
            "tap one of " + ("your" if a["mistake_type"] == "M1" else "their") + " pieces, or choose \"No immediate threat\"",
        )
    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError:
        move = None
    if move is None or move not in board.legal_moves:
        raise AssessmentError("illegal_move", "that move is not legal here")

    evidence = json.loads(current["evidence_json"])
    evidence.setdefault("engine_config_id", current["engine_config_id"])
    verdict = judge(board, move, current["kind"], evidence, analyser)
    view = conn.execute(
        "SELECT first_shown_at, shown_count FROM assessment_view WHERE assessment_id = ? AND position_id = ?",
        (assessment_id, current["position_id"]),
    ).fetchone()
    if view is None:  # answered without the server ever showing it: no time, flagged
        elapsed, interrupted = None, True
    else:
        raw = int((now - datetime.fromisoformat(view["first_shown_at"])).total_seconds() * 1000)
        elapsed = max(0, min(raw, TIME_CAP_MS))
        interrupted = view["shown_count"] > 1 or raw > TIME_CAP_MS
    try:
        conn.execute(
            "INSERT INTO assessment_result (assessment_id, position_id, recognition_response, recognition_correct, move,"
            " move_sound, elapsed_ms, interrupted, verdict_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (assessment_id, current["position_id"], recognition,
             int(recognition_correct(current["kind"], evidence, recognition)), move.uci(), int(verdict.sound), elapsed,
             int(interrupted), json.dumps({"eval_loss": verdict.eval_loss, "failed": list(verdict.failed),
                                           "move": verdict.move})),
        )
    except sqlite3.IntegrityError:
        raise AssessmentError("not_current_position", "this position is already answered") from None
    return get_assessment(conn, assessment_id, now=now)


def submit(conn: sqlite3.Connection, assessment_id: int, *, now: datetime | None = None) -> dict:
    """The final submit: every position answered, positions become TESTED (never used again), answers can be revealed."""
    a = _load(conn, assessment_id)
    if a["status"] != "submitted":
        items = _items(conn, assessment_id)
        if any(i["result_id"] is None for i in items):
            raise AssessmentError("not_finished", "answer every position before submitting")
        with transaction(conn):
            conn.execute(
                "UPDATE assessment SET status = 'submitted', submitted_at = ? WHERE id = ?", (_iso(_now(now)), assessment_id)
            )
            conn.execute(
                "UPDATE position SET exposure_status = 'TESTED' WHERE id IN"
                " (SELECT position_id FROM assessment_position WHERE assessment_id = ?)",
                (assessment_id,),
            )
    return {"assessment_id": assessment_id, "status": "submitted"}


# --- random-guess rates --------------------------------------------------------------------------------------------------


def recognition_chance(kind: str, evidence: dict, fen: str, mistake_type: str,
                       question_version: str = QUESTION_VERSION) -> float:
    """PRD §7.5 with ADR 0006 decisions 7 and 24: right answers ÷ (pieces that can be tapped + 1 for "No immediate threat").
    Version 2 counts only the side the question is about; version 1 counted every piece on the board."""
    board = chess.Board(fen)
    right = 1 if kind == "CLEAN" else len(evidence["target_squares"])
    return right / (len(tap_squares(board, mistake_type, question_version)) + 1)


def move_chance(conn: sqlite3.Connection, position_id: int, engine_config_id: str) -> float | None:
    row = conn.execute(
        "SELECT legal_moves, sound_moves FROM position_move_chance WHERE position_id = ? AND engine_config_id = ?"
        " AND sound_version = ?",
        (position_id, engine_config_id, sound.VERSION),
    ).fetchone()
    return row["sound_moves"] / row["legal_moves"] if row else None


def compute_move_chance(conn: sqlite3.Connection, position_id: int, analyser) -> float:
    """Judge every legal move of a position (slow: one engine search per move, cached) and store the share that is sound."""
    p = conn.execute("SELECT fen, kind, evidence_json, engine_config_id FROM position WHERE id = ?", (position_id,)).fetchone()
    known = move_chance(conn, position_id, p["engine_config_id"])
    if known is not None:
        return known
    board = chess.Board(p["fen"])
    evidence = json.loads(p["evidence_json"])
    evidence.setdefault("engine_config_id", p["engine_config_id"])
    moves = list(board.legal_moves)
    sound_n = sum(judge(board, m, p["kind"], evidence, analyser).sound for m in moves)
    conn.execute(
        "INSERT OR IGNORE INTO position_move_chance (position_id, engine_config_id, sound_version, legal_moves, sound_moves,"
        " computed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (position_id, p["engine_config_id"], sound.VERSION, len(moves), sound_n, _iso(_now(None))),
    )
    return sound_n / len(moves)


def missing_move_chances(conn: sqlite3.Connection, assessment_id: int) -> list[int]:
    return [i["position_id"] for i in _items(conn, assessment_id)
            if move_chance(conn, i["position_id"], i["engine_config_id"]) is None]


# --- results (only after the final submit) -------------------------------------------------------------------------------


def _piece_words(board: chess.Board, square: str) -> str:
    piece = board.piece_at(chess.parse_square(square))
    return f"{chess.piece_name(piece.piece_type)} on {square}" if piece else square


def explain(kind: str, evidence: dict, fen: str) -> str:
    """A plain-words explanation built only from the evidence record (PRD §12 template; no LLM here)."""
    board = chess.Board(fen)
    if kind == "CLEAN":
        return ("Nothing was in danger here, so the right answer was \"No immediate threat\". "
                "Any move that kept the game about level was fine.")
    # Only the capture is named: the rest of the engine's line is one illustration among many, not forced (PRD §12).
    capture = evidence["refutation_line"]["san"][0]
    played = evidence["player_move"]["san"]
    n = evidence["material_swing"]
    if evidence["mistake_type"] == "M1":
        target = _piece_words(board, evidence["target_squares"][0])
        return (f"Your {target} was in danger. In the game you played {played}, and they could take it with {capture}, "
                f"winning {n} points of material.")
    target = " or ".join(_piece_words(board, s) for s in evidence["target_squares"])
    return (f"Their {target} could be won: {capture} wins you {n} points of material. "
            f"In the game you played {played} instead.")


_REASONS = {
    "refutation_still_wins": "they could still win the piece",
    "free_piece_not_taken": "the free piece was left and the move gave away too much",
    "eval_loss_too_large": "it gave away too much",
}


def _move_words(verdict: dict, sound_: bool) -> str:
    san = verdict["move"]["san"]
    if sound_:
        return f"Your move {san} was sound."
    reasons = [_REASONS[c] for c in verdict["failed"] if c in _REASONS]
    if "refutation_still_wins" in verdict["failed"]:
        reasons = [_REASONS["refutation_still_wins"]]
    return f"Your move {san} was not sound: {reasons[0] if reasons else 'it gave away too much'}."


def left_out_reason(kind: str, board: chess.Board, *, conn: sqlite3.Connection | None = None,
                    engine_config_id: str | None = None) -> str | None:
    """Why a position is left out of the score, in plain words, or None. Only a "nothing is wrong" position can be unfair:
    a capture that wins anything for either side (or a check) makes "No immediate threat" the wrong answer. It is judged by
    the whole current CLEAN rule, so a position chosen under the looser v1 rule is left out of the score whichever way the
    player answered (abstain rather than guess, AGENTS rule 5): the engine-free part (`clean.threat_reason`) and the engine's
    best line, read from the position's own cached search (`clean.best_line_reason`). A position whose search is not in the
    cache cannot be judged on the engine part and stays in."""
    if kind != "CLEAN":
        return None
    why = clean.threat_reason(board)
    if why is None and conn is not None and engine_config_id is not None:
        why = clean.best_line_reason(board, cached_analysis(conn, board.fen(), engine_config_id))
    if why is None:
        return None
    return (f"Left out of your score: {LEFT_OUT_WORDS[why]}, so \"No immediate threat\" was not a fair answer. "
            "That is a flaw in how this position was chosen, not in your play.")


def results(conn: sqlite3.Connection, assessment_id: int) -> dict:
    """Answers, explanations and scores with their random-guess rates. Only after the final submit."""
    a = _load(conn, assessment_id)
    if a["status"] != "submitted":
        raise AssessmentError("not_submitted", "answers are shown only after all positions are submitted")
    rows = conn.execute(
        "SELECT ap.ord, p.id AS position_id, p.fen, p.kind, p.evidence_json, p.verified_alternatives_json,"
        " p.engine_config_id, r.recognition_response, r.recognition_correct, r.move, r.move_sound, r.elapsed_ms,"
        " r.interrupted, r.verdict_json"
        " FROM assessment_position ap JOIN position p ON p.id = ap.position_id"
        " JOIN assessment_result r ON r.assessment_id = ap.assessment_id AND r.position_id = ap.position_id"
        " WHERE ap.assessment_id = ? ORDER BY ap.ord",
        (assessment_id,),
    ).fetchall()
    items = []
    for r in rows:
        evidence = json.loads(r["evidence_json"])
        verdict = json.loads(r["verdict_json"])
        board = chess.Board(r["fen"])
        out = left_out_reason(r["kind"], board, conn=conn, engine_config_id=r["engine_config_id"])
        if r["kind"] == "CLEAN":
            good_moves = [evidence["best_move"]]
            answer: list[str] = []
            line = None
        else:
            good_moves = json.loads(r["verified_alternatives_json"] or "[]") or [evidence["best_move"]]
            answer = evidence["target_squares"]
            line = evidence["refutation_line"]
        items.append({
            "number": r["ord"] + 1,
            "fen": r["fen"],
            "side_to_move": "white" if board.turn == chess.WHITE else "black",
            "kind": r["kind"],
            "answer_squares": answer,
            "your_tap": r["recognition_response"],
            "tap_correct": bool(r["recognition_correct"]),
            "your_move": verdict["move"],
            "move_sound": bool(r["move_sound"]),
            "correct": bool(r["recognition_correct"] and r["move_sound"]),
            "explanation": out or explain(r["kind"], evidence, r["fen"]),
            "move_explanation": _move_words(verdict, bool(r["move_sound"])),
            "good_moves": [{"uci": m["uci"], "san": m["san"]} for m in good_moves],
            "game_move": evidence["player_move"],
            "line": line,  # MISTAKE: the refutation (M1, played after the game move) or the capture (M2)
            "seconds": None if r["elapsed_ms"] is None else round(r["elapsed_ms"] / 1000),
            "interrupted": bool(r["interrupted"]),
            "recognition_chance": recognition_chance(r["kind"], evidence, r["fen"], a["mistake_type"], a["question_version"]),
            "move_chance": move_chance(conn, r["position_id"], r["engine_config_id"]),
            "left_out": out,
        })
    scored = [i for i in items if i["left_out"] is None]
    n = len(scored)
    pending = any(i["move_chance"] is None for i in scored)
    rec_chance = sum(i["recognition_chance"] for i in scored)
    move_chance_sum = None if pending else sum(i["move_chance"] for i in scored)
    both_chance = None if pending else sum(i["recognition_chance"] * i["move_chance"] for i in scored)
    return {
        "assessment_id": a["id"],
        "assessment_kind": a["kind"],
        "mistake_type": a["mistake_type"],
        "label": LABELS[a["mistake_type"]],
        "question_version": a["question_version"],
        "notes": [V1_NOTE] if a["question_version"] == "1" else [],
        "set_aside": a["superseded_at"] is not None,
        "submitted_at": a["submitted_at"],
        "total": n,  # positions that count: a position left out (below) is in neither the score nor the denominator
        "left_out_count": len(items) - n,
        "scores": {
            "recognition": sum(i["tap_correct"] for i in scored),
            "move": sum(i["move_sound"] for i in scored),
            "combined": sum(i["correct"] for i in scored),
        },
        # expected number right out of `total` when guessing at random (PRD §7.5); combined assumes the two guesses are
        # independent
        "chance": {
            "recognition": round(rec_chance, 2),
            "move": None if move_chance_sum is None else round(move_chance_sum, 2),
            "combined": None if both_chance is None else round(both_chance, 2),
        },
        "chance_pending": pending,
        "interrupted": sum(i["interrupted"] for i in scored),
        "items": items,
        "versions": {"sound": sound.VERSION, "rules": R.RULES_VERSION, "clean": clean.VERSION},
    }


# --- setting a baseline aside --------------------------------------------------------------------------------------------


def supersede_baseline(conn: sqlite3.Connection, assessment_id: int, reason: str, *, now: datetime | None = None) -> dict:
    """Set a submitted baseline aside so the type can be taken again (ADR 0006 decision 25). Nothing is deleted: the answers
    stay, its positions stay TESTED and are never used again, and it simply stops being the baseline."""
    a = _load(conn, assessment_id)
    if a["kind"] != "BASELINE":
        raise AssessmentError("not_a_baseline", "only a baseline can be set aside")
    if a["status"] != "submitted":
        raise AssessmentError("not_finished", "only a submitted assessment can be set aside")
    if a["superseded_at"] is not None:
        raise AssessmentError("already_set_aside", "this baseline is already set aside")
    if not reason.strip():
        raise AssessmentError("reason_needed", "say why it is set aside")
    conn.execute(
        "UPDATE assessment SET superseded_at = ?, superseded_reason = ? WHERE id = ?",
        (_iso(_now(now)), reason.strip(), assessment_id),
    )
    return {"assessment_id": assessment_id, "mistake_type": a["mistake_type"], "set_aside": True}


def main(argv: list[str] | None = None) -> int:
    import argparse

    from app.db.schema import connect

    parser = argparse.ArgumentParser(prog="python -m app.learner.assessment")
    sub = parser.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("supersede", help="set a submitted baseline aside so it can be retaken (nothing is deleted)")
    one.add_argument("assessment_id", type=int)
    one.add_argument("--reason", required=True)
    sub.add_parser("list", help="list assessments")
    args = parser.parse_args(argv)
    conn = connect()
    if args.cmd == "list":
        for r in conn.execute("SELECT id, mistake_type, kind, status, question_version, superseded_at FROM assessment"):
            print(dict(r))
        return 0
    print(supersede_baseline(conn, args.assessment_id, args.reason))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
