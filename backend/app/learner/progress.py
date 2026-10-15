"""The Progress screen's data (PRD v2 §7.6, §13, Step 4): did practice help, per mistake type.

Everything is a count with its denominator, and the unassisted and assisted results are kept apart (AGENTS rules 3 and 4):

- **Tests (unassisted):** the starting test and each delayed test, from `assessment.results()` (so the same scores, random-guess
  rates and left-out positions as the results page), with the mean decision time. A set-aside baseline is not the baseline.
- **Comparison:** the starting test against the delayed tests. The move score is always comparable. The tap and combined scores
  only when the question wording is the same in both (a version 1 test's tap score is not comparable, ADR 0006 decision 24).
  Gain over the baseline is shown in positions out of 5 (PRD §13) with the guessing level beside it; it is directional, not proof.
- **Practice (assisted):** sessions, first-attempt results, hint dependence, decision time, and the most common reasons a move
  was not sound. Never mixed into the test scores.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime

from app.learner import assessment as A

# One main reason per not-sound move (`assessment.reason_code`, the same function the feedback sentence uses), so the counts add up.
REASON_WORDS = {
    "refutation_still_wins": "the piece was still in danger after the move",
    "free_piece_not_taken": "the free piece was left",
    "allows_checkmate": "the move allowed checkmate",
    "missed_checkmate": "a forced checkmate was missed",
    "eval_loss_too_large": "a stronger move existed",
}


def _test_summary(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    r = A.results(conn, row["id"])
    # an interrupted position is capped at 300 s (PRD §7.4): it is flagged, and kept out of the average
    counted = [i for i in r["items"] if not i["left_out"] and not i["interrupted"] and i["seconds"] is not None]
    seconds = [i["seconds"] for i in counted]
    return {
        "assessment_id": row["id"], "kind": row["kind"], "submitted_at": row["submitted_at"],
        "question_version": r["question_version"], "total": r["total"], "left_out_count": r["left_out_count"],
        "scores": r["scores"], "chance": r["chance"], "chance_pending": r["chance_pending"],
        "mean_seconds": round(sum(seconds) / len(seconds)) if seconds else None, "timed": len(seconds),
        "interrupted": r["interrupted"],
    }


def _accuracy(summary: dict, key: str) -> float | None:
    return summary["scores"][key] / summary["total"] if summary["total"] else None


def comparison(baseline: dict | None, delayed: list[dict]) -> dict | None:
    """The starting test against the delayed tests (PRD §7.6, §13). None until a delayed test is done."""
    if baseline is None or not delayed or not baseline["total"]:
        return None
    out: dict = {"baseline": {"move": _accuracy(baseline, "move"), "total": baseline["total"]}, "delayed": [],
                 "comparable": {"move": True, "recognition": True}}
    for d in delayed:
        same = d["question_version"] == baseline["question_version"]
        out["comparable"]["recognition"] = out["comparable"]["recognition"] and same
        out["delayed"].append({"assessment_id": d["assessment_id"], "total": d["total"], "move": _accuracy(d, "move"),
                               "recognition": _accuracy(d, "recognition") if same else None,
                               "combined": _accuracy(d, "combined") if same else None})
    moves = [x["move"] for x in out["delayed"] if x["move"] is not None]
    if moves:
        out["gain_move_positions_of_5"] = round((sum(moves) / len(moves) - out["baseline"]["move"]) * A.SIZE, 1)
    both = [x["combined"] for x in out["delayed"] if x["combined"] is not None]
    base_combined = _accuracy(baseline, "combined")
    if both and out["comparable"]["recognition"] and base_combined is not None:
        out["gain_combined_positions_of_5"] = round((sum(both) / len(both) - base_combined) * A.SIZE, 1)
    return out


def practice_stats(conn: sqlite3.Connection, mistake_type: str) -> dict:
    """Assisted practice for one type. Attempts count only when the move was made."""
    sessions = conn.execute(
        "SELECT COUNT(*) FROM practice_session WHERE user = ? AND mistake_type = ? AND status = 'completed'",
        (A.user(), mistake_type)).fetchone()[0]
    rows = conn.execute(
        "SELECT a.position_id, a.attempt_number, a.move_sound, a.hint_level, a.elapsed_ms, a.recognition_correct, a.verdict_json,"
        " p.fen, p.engine_config_id FROM practice_attempt a JOIN practice_session s ON s.id = a.session_id"
        " JOIN position p ON p.id = a.position_id"
        " WHERE s.user = ? AND s.mistake_type = ? AND a.move IS NOT NULL ORDER BY a.id", (A.user(), mistake_type)).fetchall()
    first = [r for r in rows if r["attempt_number"] == 1]
    seconds = [r["elapsed_ms"] / 1000 for r in first if r["elapsed_ms"] is not None]
    reasons: Counter = Counter()
    for r in rows:
        if not r["move_sound"]:
            code = A.reason_code(A.with_mate(conn, json.loads(r["verdict_json"]), r["fen"], r["engine_config_id"]))
            if code:
                reasons[code] += 1
    not_sound = sum(1 for r in rows if not r["move_sound"])
    return {
        "assisted": True, "sessions": sessions, "positions": len({r["position_id"] for r in rows}),
        "first_attempts": len(first),
        "first_attempt_correct": sum(1 for r in first if r["move_sound"] == 1 and r["hint_level"] == 0),
        "assisted_correct": sum(1 for r in first if r["move_sound"] == 1 and r["hint_level"] > 0),
        "recognized": sum(1 for r in first if r["recognition_correct"] == 1 and r["hint_level"] == 0),
        "attempts": len(rows), "retries": sum(1 for r in rows if r["attempt_number"] > 1),
        "attempts_with_hint": sum(1 for r in rows if r["hint_level"] > 0),
        "mean_first_seconds": round(sum(seconds) / len(seconds)) if seconds else None,
        "not_sound": not_sound,
        "reasons": [{"reason": REASON_WORDS[c], "count": n} for c, n in reasons.most_common()],
    }


def progress(conn: sqlite3.Connection, *, now: datetime | None = None) -> dict:
    now = A._now(now)
    types = []
    for t in A.TYPES:
        rows = conn.execute(
            "SELECT id, kind, submitted_at, superseded_at FROM assessment WHERE user = ? AND mistake_type = ?"
            " AND status = 'submitted' ORDER BY id", (A.user(), t)).fetchall()
        baseline_rows = [r for r in rows if r["kind"] == "BASELINE" and r["superseded_at"] is None]
        baseline = _test_summary(conn, baseline_rows[-1]) if baseline_rows else None
        delayed = [_test_summary(conn, r) for r in rows if r["kind"] == "DELAYED"]
        waiting = A.waiting_assessment(conn, t, now)
        types.append({
            "mistake_type": t, "label": A.LABELS[t], "baseline": baseline, "delayed": delayed,
            "set_aside": sum(1 for r in rows if r["superseded_at"] is not None),
            "waiting": None if waiting is None else {
                "assessment_id": waiting["assessment_id"], "due_at": waiting["due_at"], "available": waiting["available"],
            },
            "comparison": comparison(baseline, delayed), "practice": practice_stats(conn, t),
        })
    return {"types": types, "targets_delayed_per_type": 3}
