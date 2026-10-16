"""Practice mode as chat tools (docs/mcp-practice-plan.md §5 to §7). Words only: every function takes a store connection and
returns one markdown message. Scoring, selection and the engine check all live in `learner/practice.py`; nothing here decides
anything about chess (PRD §11, AGENTS rule 1). A refused step comes back as a sentence, never a traceback."""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager

import chess

from app.learner import assessment as A
from app.learner import practice as P
from app.learner import progress as G
from app.mcp.board_text import piece_list, render_board

log = logging.getLogger(__name__)

Opener = Callable[[sqlite3.Connection], AbstractContextManager]  # starts the analyser for one move check

TYPE_NAMES = {"pieces_in_danger": "M1", "free_pieces": "M2", "m1": "M1", "m2": "M2"}
NO_THREAT_WORDS = {"none", "no", "no threat", "no immediate threat", "nothing", "no danger"}
_UCI = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")
_SQUARE = re.compile(r"^[a-h][1-8]$")


class Refused(Exception):
    """A step the tool will not take, with the sentence to show."""


def _refusal(text: str) -> str:
    return f"I could not do that: {text}"


def _guard(fn: Callable[[], str]) -> str:
    try:
        return fn()
    except Refused as e:
        return _refusal(str(e))
    except A.AssessmentError as e:
        if e.code == "wrong_step":
            return _refusal(f"{e}. Use practice_show to see where you are.")
        if e.code == "not_current_position":
            return _refusal("that is not the position on the board. Use practice_show to see it.")
        return _refusal(str(e))
    except (sqlite3.Error, OSError, ValueError, RuntimeError):  # no paths, SQL or traceback in the chat
        log.exception("practice tool failed")
        return _refusal("something went wrong on my side. Your practice so far is saved; try practice_show.")


# --- reading the state ---------------------------------------------------------------------------------------------------


def _view(conn: sqlite3.Connection, session_id: int) -> dict:
    try:
        return P.get_session(conn, session_id)
    except A.AssessmentError as e:
        raise Refused(f"there is no practice session {session_id}. Use practice_status to find yours.") from e


def _current(conn: sqlite3.Connection, session_id: int) -> tuple[dict, dict]:
    view = _view(conn, session_id)
    cur = view["current"]
    if cur is None:
        raise Refused("this session is finished. Use practice_summary to see it.")
    return view, cur


def _tap_side(view: dict, cur: dict) -> str:
    mine = cur["side_to_move"]
    other = "black" if mine == "white" else "white"
    return mine if view["mistake_type"] == "M1" else other


def _hint_marks(cur: dict) -> list[str]:
    out: list[str] = []
    for h in cur["hints"]:
        out += h.get("squares", [])
    return out


def _delayed_line(d: dict) -> str:
    if d["status"] == "scheduled":
        return f"Your delayed test is set and opens {d['due_at']} (UTC). It uses positions you have not seen, with no help. Take it in the web app."
    if d["status"] == "pending_exists":
        when = f" It opens {d['due_at']} (UTC)." if d.get("due_at") else ""
        return f"Another test was already waiting when you finished, so none was set for this session.{when}"
    if d["status"] == "no_positions":
        return "No unused positions were left to set a delayed test for this mistake type."
    if d["status"] == "error":
        return "Something went wrong setting your delayed test, so none was set. Your practice was saved."
    return "No delayed test was set for this session."


def render_session(conn: sqlite3.Connection, session_id: int) -> str:
    """The session as the player may see it now, for whichever stage it is at."""
    view = _view(conn, session_id)
    cur = view["current"]
    if cur is None:
        return _render_finished(conn, session_id)
    head = (f"**{view['label']}: position {cur['number']} of {view['total']}** (try {cur['attempt']}) · session "
            f"{view['session_id']} · assisted practice")
    stage = cur["stage"]
    fb = cur["feedback"]
    marks = fb["target_squares"] if fb else _hint_marks(cur)
    board = render_board(cur["fen"], cur["side_to_move"], marks)
    parts = [head, f"You play {cur['side_to_move']} and it is your move.",
             "```\n" + board + f"\nFEN: {cur['fen']}\n```"]
    if marks:
        parts.append("Squares in [brackets] are the ones to look at.")
    if stage == "recognition":
        ask = ("Which of YOUR pieces can the other side win?" if view["mistake_type"] == "M1"
               else "Which of THEIR pieces can you win for free?")
        side = _tap_side(view, cur)
        parts += [f"**Step 1, a question first (not a move yet).** {ask}",
                  'Reply with its square (for example g5), or say "no immediate threat".',
                  f"Pieces you can name ({side}): {piece_list(cur['fen'], side)}.",
                  "Use practice_answer with the square, or \"none\"."]
    elif stage == "move":
        parts += [f"Your answer: {_tap_words(cur['your_tap'])}.",
                  "**Step 2, your move.** Use practice_move with a move such as Nf3, Bxe5, O-O, or g1f3."]
    else:
        parts += _feedback_lines(fb)
    if cur["hints"]:
        parts += [f"Hint {h['level']}: {h['text']}" for h in cur["hints"]]
    if stage != "feedback":
        left = 3 - cur["hint_level"]
        parts.append(f"Hints are optional ({left} left): practice_hint." if left else "No hints left.")
    return "\n\n".join(parts)


def _tap_words(tap: str | None) -> str:
    if tap is None:
        return "none yet"
    return '"No immediate threat"' if tap == A.NO_THREAT else f"the piece on {tap}"


def _feedback_lines(fb: dict) -> list[str]:
    lines = [f"**Your move {fb['your_move']['san']}: {fb['verdict']}.** {fb['avoids']}",
             f"You chose {_tap_words(fb['your_tap'])}: {'right' if fb['tap_correct'] else 'not right'}.",
             fb["original"], fb["allowed"]]
    if not fb["sound"] and fb["good_moves"]:
        lines.append("Good moves here: " + ", ".join(m["san"] for m in fb["good_moves"]) + ".")
    lines.append("Use practice_retry to try this position again, or practice_next to go on.")
    return lines


def _render_finished(conn: sqlite3.Connection, session_id: int) -> str:
    s = P.summary(conn, session_id)
    out = [f"**{s['label']}: session {s['session_id']} finished** · assisted practice (not a test score)",
           f"Positions completed: {s['completed']} of {s['total']}",
           f"Right on the first try with no hint: {s['first_attempt_correct']}",
           f"Right on the first try with a hint: {s['assisted_correct']}",
           f"Needed another try: {s['needed_retry']}",
           f"Spotted the problem yourself, with no hint: {s['recognized']}"]
    if s["repeat_games"]:
        out.append("Some positions came from the same game.")
    out.append("")
    for it in s["items"]:
        tag = ("right first try, no hint" if it["first_attempt_correct"] else
               "right with a hint" if it["assisted_correct"] else "not right on the first try")
        out.append(f"Position {it['number']} ({tag}, {it['attempts']} {'try' if it['attempts'] == 1 else 'tries'}): {it['original']}")
    out += ["", "**Next:** " + _delayed_line(s["delayed_test"])]
    return "\n".join(out)


# --- the tools -----------------------------------------------------------------------------------------------------------


def practice_status(conn: sqlite3.Connection) -> str:
    def run() -> str:
        lines = []
        for t in A.home(conn)["types"]:
            p = P.home_status(conn, t["mistake_type"])
            name = f"{t['label']} (`{'pieces_in_danger' if t['mistake_type'] == 'M1' else 'free_pieces'}`)"
            if not p["unlocked"]:
                state = "locked: take the starting test in the web app first."
            elif p["session"]:
                state = f"open session {p['session']['session_id']}, {p['session']['done']} of {p['session']['total']} done."
            else:
                pos = p["positions"]
                left = pos["unseen"] + pos["to_repeat"]
                state = (f"ready, {pos['unseen']} new and {pos['to_repeat']} to repeat." if left >= P.MIN_SIZE
                         else f"not enough positions left ({left}; at least {P.MIN_SIZE} are needed).")
            w = t["delayed"]["waiting"]
            if w:
                state += (" Delayed test: open now, take it in the web app." if w["available"]
                          else f" Delayed test opens {w['due_at']} (UTC).")
            lines.append(f"- {name}: {state}")
        return "**Practice status** (practice is always assisted)\n\n" + "\n".join(lines)
    return _guard(run)


def practice_start(conn: sqlite3.Connection, mistake_type: str) -> str:
    def run() -> str:
        t = TYPE_NAMES.get(str(mistake_type).strip().lower())
        if t is None:
            raise Refused("mistake_type must be pieces_in_danger or free_pieces.")
        started = P.start_session(conn, t)
        return render_session(conn, started["session_id"])
    return _guard(run)


def practice_show(conn: sqlite3.Connection, session_id: int) -> str:
    return _guard(lambda: render_session(conn, session_id))


def _parse_square(text: str) -> str:
    word = " ".join(str(text).strip().lower().replace("-", " ").split())
    if word in NO_THREAT_WORDS:
        return A.NO_THREAT
    if _SQUARE.match(word):
        return word
    raise Refused('give a square such as g5, or say "none" for no immediate threat.')


def practice_answer(conn: sqlite3.Connection, session_id: int, square: str) -> str:
    def run() -> str:
        _, cur = _current(conn, session_id)
        P.submit_recognition(conn, session_id, cur["ord"], _parse_square(square))
        return render_session(conn, session_id)
    return _guard(run)


def parse_move(board: chess.Board, text: str) -> chess.Move:
    """UCI first, then SAN (as written, then with the piece letter capitalised, so `bf4` means `Bf4`; `0-0` is `O-O`). The
    result is always a legal move on `board`, or a Refused with the reason in words."""
    raw = str(text).strip()
    if not raw:
        raise Refused("give a move such as Nf3, O-O or g1f3.")
    if _UCI.match(raw.lower()):
        move = chess.Move.from_uci(raw.lower())
        if move in board.legal_moves:
            return move
        if len(raw) == 4:  # a pawn reaching the last rank without a piece letter
            promo = chess.Move.from_uci(raw.lower() + "q")
            if promo in board.legal_moves:
                raise Refused(f"{raw} promotes a pawn: add the piece, for example {raw.lower()}q.")
        raise Refused(f"{raw} is not a legal move here.")
    san = raw.replace("0-0-0", "O-O-O").replace("0-0", "O-O").rstrip("+#!?")
    candidates = [san]
    if san and san[0] in "bnrqk":  # lowercase piece letter (a pawn capture like bxc3 is tried first as written)
        candidates.append(san[0].upper() + san[1:])
    ambiguous = False
    illegal = None
    for cand in candidates:
        try:
            return board.parse_san(cand)
        except chess.AmbiguousMoveError:
            ambiguous = True
        except chess.IllegalMoveError:
            illegal = cand
        except chess.InvalidMoveError:
            pass
    if ambiguous:
        raise Refused(f"{raw} could be more than one piece: add the square it starts from, for example Nbd2 or g1f3.")
    if illegal:
        raise Refused(f"{illegal} is not a legal move here.")
    raise Refused(f"I could not read \"{raw}\" as a move. Use a move such as Nf3, O-O or g1f3.")


def practice_move(conn: sqlite3.Connection, session_id: int, move: str, opener: Opener) -> str:
    def run() -> str:
        _, cur = _current(conn, session_id)
        if cur["stage"] != "move":  # say so before parsing: the move may be right for a step we are not at
            raise A.AssessmentError("wrong_step", f"this position is at the {cur['stage']} step")
        parsed = parse_move(chess.Board(cur["fen"]), move)
        with opener(conn) as analyser:
            P.submit_move(conn, session_id, cur["ord"], parsed.uci(), analyser)
        return render_session(conn, session_id)
    return _guard(run)


def practice_hint(conn: sqlite3.Connection, session_id: int) -> str:
    def run() -> str:
        _, cur = _current(conn, session_id)
        if cur["stage"] == "feedback":
            raise A.AssessmentError("wrong_step", "this position is at the feedback step")
        if cur["hint_level"] >= 3:
            raise Refused("you have used all three hints on this try.")
        P.hint(conn, session_id, cur["ord"])
        return render_session(conn, session_id)
    return _guard(run)


def practice_retry(conn: sqlite3.Connection, session_id: int) -> str:
    def run() -> str:
        _, cur = _current(conn, session_id)
        P.retry(conn, session_id, cur["ord"])
        return render_session(conn, session_id)
    return _guard(run)


def practice_next(conn: sqlite3.Connection, session_id: int) -> str:
    def run() -> str:
        _, cur = _current(conn, session_id)
        P.next_position(conn, session_id, cur["ord"])
        return render_session(conn, session_id)
    return _guard(run)


def practice_summary(conn: sqlite3.Connection, session_id: int) -> str:
    def run() -> str:
        # no `_view` here: opening a session writes its first attempt, and this tool must change nothing
        try:
            return _render_finished(conn, session_id)
        except A.AssessmentError as e:
            if e.code == "not_found":
                raise Refused(f"there is no practice session {session_id}. Use practice_status to find yours.") from e
            raise Refused("the summary is shown when the session is finished. Use practice_show to carry on.") from e
    return _guard(run)


def _chance(n: float | None) -> str:
    if n is None:
        return "guessing: still calculating"
    return "guessing would get almost none" if n < 0.05 else f"guessing would get about {n:.1f}"


def progress(conn: sqlite3.Connection) -> str:
    def run() -> str:
        out = ["**My progress.** Tests (no help) and assisted practice are kept apart. Five positions show direction, not proof."]
        for t in G.progress(conn)["types"]:
            out.append(f"\n### {t['label']}")
            b = t["baseline"]
            if b is None:
                out.append("Starting test: not done yet (web app).")
            else:
                out.append(f"Starting test, played a sound move: {b['scores']['move']} of {b['total']} ({_chance(b['chance']['move'])})")
            for i, d in enumerate(t["delayed"], 1):
                out.append(f"Delayed test {i}, played a sound move: {d['scores']['move']} of {d['total']} ({_chance(d['chance']['move'])})")
            c = t["comparison"]
            if c and "gain_move_positions_of_5" in c:
                out.append(f"Change in sound moves, starting test to delayed tests: {c['gain_move_positions_of_5']:+.1f} positions out of 5.")
            w = t["waiting"]
            if w:
                out.append("A delayed test is open now: take it in the web app." if w["available"]
                           else f"A delayed test opens {w['due_at']} (UTC).")
            p = t["practice"]
            out.append(f"Assisted practice: {p['sessions']} sessions, {p['first_attempts']} first attempts; right with no hint "
                       f"{p['first_attempt_correct']}, right with a hint {p['assisted_correct']}, extra tries {p['retries']}.")
            for r in p["reasons"]:
                out.append(f"- not sound because {r['reason']}: {r['count']}")
        return "\n".join(out)
    return _guard(run)
