"""Games against Stockfish as chat tools (ADR 0009). Words and data only: every function calls the shared tool layer
`app.api.tools` (the one behind the web API) and decides nothing about chess (AGENTS rule 1).

Rule 4 (ADR 0005): help for the player exists only in Practice. A Play game's data is built from the allow-list `PLAY_KEYS` and
its text from status, the move record and the letter board; the help tools refuse in Play and return no data. Practice adds one
nested `practice` object. A refused step comes back as a sentence, never a traceback."""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict

import chess

from app.api import tools as T
from app.api.store import GAMES
from app.core.game import Game, GameError, Mode
from app.engine.stockfish import EngineError
from app.mcp.board_text import render_board

log = logging.getLogger(__name__)

REFUSAL_PREFIX = "I could not do that: "
MAX_GAMES = 20  # chat games kept in memory; starting one more drops the oldest

# The only keys a Play game's data may have. Everything that helps the player lives under `practice`, which Play never has.
PLAY_KEYS = ("id", "fen", "moves", "revision", "turn", "user_color", "mode", "engine_level", "outcome", "legal_moves")
PRACTICE_KEYS = ("assisted", "hints_used", "can_take_back", "show_threats", "threats", "feedback", "hint")

_UCI = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")
_REFUSALS = {
    "not_found": "there is no such game here. Games started in the web app, or before the server restarted, are not available.",
    "feedback_not_allowed": "that help is only available in Practice mode.",
    "takeback_not_allowed": "undo is only available in Practice mode.",
    "nothing_to_take_back": "there is no move of yours to take back.",
    "game_over": "that game has ended.",
    "not_your_turn": "it is the opponent's turn.",
    "no_hint": "a hint is only available on your turn in a game still being played.",
    "revision_conflict": "the board changed since you looked. Use game_show to see it.",
}

_lock = threading.Lock()
_OWNED: OrderedDict[str, dict] = OrderedDict()  # game id -> per-game chat state (the threat toggle, cached feedback)


class Refused(Exception):
    """A step the tool will not take, with the sentence to show."""


def is_refusal(text: str) -> bool:
    return text.startswith(REFUSAL_PREFIX)


def refusal(text: str) -> str:
    return REFUSAL_PREFIX + text


_idle_seconds: float | None = None  # None: games are kept until pushed out by MAX_GAMES (the owner's server); the open server sets it
_seen: dict[str, float] = {}  # game id -> last time a tool touched it


def configure(max_games: int, idle_seconds: float | None) -> None:
    """The open server holds many players' games, so it keeps more of them and forgets idle ones."""
    global MAX_GAMES, _idle_seconds
    MAX_GAMES, _idle_seconds = max_games, idle_seconds


def _forget(gid: str) -> None:
    _OWNED.pop(gid, None)
    _seen.pop(gid, None)
    GAMES.pop(gid, None)


def _expire(now: float) -> None:
    """Drop games untouched for `_idle_seconds`. Caller holds `_lock`."""
    if _idle_seconds is None:
        return
    for gid in [g for g, t in _seen.items() if now - t > _idle_seconds]:
        _forget(gid)


def _own(game_id: str) -> Game:
    """The game, only if this server started it (and has not forgotten it)."""
    now = time.monotonic()
    with _lock:
        _expire(now)
        known = game_id in _OWNED
        if known:
            _seen[game_id] = now
    game = GAMES.get(game_id) if known else None
    if game is None:
        raise Refused(_REFUSALS["not_found"])
    return game


def reset() -> None:
    """Forget every chat game (tests)."""
    with _lock:
        for gid in list(_OWNED):
            _forget(gid)


def _guard(fn):
    try:
        return fn()
    except Refused as e:
        return None, refusal(str(e))
    except GameError as e:
        return None, refusal(_REFUSALS.get(e.code) or str(e))
    except EngineError:
        log.exception("engine failed in a game tool")
        return None, refusal("the engine did not answer. Try game_show, then the move again.")


# --- data -------------------------------------------------------------------------------------------------------------------

def _san_moves(game: Game) -> list[str]:
    board, out = chess.Board(game.start_fen), []
    for uci in game.moves:
        move = chess.Move.from_uci(uci)
        out.append(board.san(move))
        board.push(move)
    return out


def _feedback(game: Game, gid: str) -> dict | None:
    """The verdict on the player's latest move, Practice only; cached per move list. Never lets a failed search lose the move."""
    mine = [i for i in range(len(game.moves)) if (i % 2 == 0) == (game.user_color == chess.WHITE)]
    if not mine:
        return None
    ply, key = mine[-1], tuple(game.moves[: mine[-1] + 1])
    with _lock:
        hit = _OWNED[gid].get("feedback")
    if hit is not None and hit[0] == key:
        return hit[1]
    try:
        fb = {**T.move_feedback(gid, ply), "prefix": list(key)}
    except (GameError, EngineError):
        log.exception("could not judge the move")
        return None
    with _lock:
        if gid in _OWNED:
            _OWNED[gid]["feedback"] = (key, fb)  # only the latest is kept
    return fb


def data(gid: str, hint: dict | None = None, judge: bool = True) -> dict:
    """What the interactive board draws. Play: the allow-listed view only. Practice: the same plus one `practice` object."""
    game = _own(gid)
    view = T.game_view(game)
    out: dict = {"kind": "game", "game": {k: view[k] for k in PLAY_KEYS}}
    if game.mode is Mode.PRACTICE:
        with _lock:
            show = _OWNED[gid].get("show_threats", True)
        extra = {"assisted": view["assisted"], "hints_used": view["hints_used"], "can_take_back": view["can_take_back"],
                 "show_threats": show, "threats": None, "feedback": _feedback(game, gid) if judge else None, "hint": hint}
        if show:
            try:
                extra["threats"] = T.current_threats(gid)
            except GameError:
                pass
        out["practice"] = extra
    return out


def text(gid: str, note: str = "") -> str:
    """The tool's words: status, the move record and the letter board (all a client without app support gets). Play text carries
    nothing but those; Practice adds the verdict headline when the feedback is there."""
    game = _own(gid)
    view = T.game_view(game)
    sans = _san_moves(game)
    pairs = [f"{i // 2 + 1}. {' '.join(sans[i:i + 2])}" for i in range(0, len(sans), 2)]
    mode = "Practice (assisted)" if game.mode is Mode.PRACTICE else "Play"
    colour = view["user_color"]
    o = view["outcome"]
    if o:
        status = f"Game over: {o['result']} ({o['termination'].replace('_', ' ')})."
    elif view["turn"] == colour:
        status = "Your move."
    else:
        status = "The opponent is to move."
    lines = [f"Game {gid}, {mode} against Stockfish level {view['engine_level']}. You are {colour}. {status}"]
    if note:
        lines.append(note)
    lines += ["Moves: " + (" ".join(pairs) if pairs else "none yet"), "```", render_board(view["fen"], colour), "```", f"FEN: {view['fen']}"]
    if game.mode is Mode.PRACTICE:
        lines.append(f"Hints used on {view['hints_used']} position(s).")
    return "\n".join(lines)


def _result(gid: str, note: str = "", hint: dict | None = None, judge: bool = True):
    """(structured data, text) for a game just acted on. `judge=False` leaves out the verdict on the player's move (it takes an
    engine search): the board's first step must return at once, and the next step carries the verdict."""
    d = data(gid, hint, judge)
    note_parts = [note] if note else []
    fb = d.get("practice", {}).get("feedback") if "practice" in d else None
    if fb:
        note_parts.append(f"Verdict on your last move: {fb['headline']}")
    return d, text(gid, " ".join(note_parts))


# --- tools ------------------------------------------------------------------------------------------------------------------

def _remember(game: Game) -> None:
    now = time.monotonic()
    with _lock:
        _expire(now)
        _OWNED[game.id] = {"show_threats": True}
        _seen[game.id] = now
        while len(_OWNED) > MAX_GAMES:
            _forget(next(iter(_OWNED)))


ENGINE_DOWN = "Stockfish did not answer. Your move is saved; use game_show to ask it again."


def _engine_turn(game: Game) -> bool:
    return game.outcome() is None and game.board().turn != game.user_color


def _reply(gid: str) -> str:
    """Let the engine play if it is its turn (idempotent). Returns a note: what it played, or that it did not answer."""
    game = _own(gid)
    before = len(game.moves)
    if not _engine_turn(game):
        return ""
    try:
        T.engine_reply(gid)
    except EngineError:
        log.exception("engine failed in a game tool")
        return ENGINE_DOWN
    return f"Stockfish replied {_san_moves(game)[-1]}." if len(game.moves) > before else ""


def game_new(color: str = "white", level: int = 3, mode: str = "play"):
    def run():
        game = T.create_game(color, mode, level)  # kept by id: the opening search below may fail, and games can start concurrently
        _remember(game)
        return _result(game.id, _reply(game.id).replace("replied", "opened with"))
    return _guard(run)


def game_show(game_id: str):
    """The board; if the engine owes a reply (an earlier search failed) it plays it now."""
    def run():
        _own(game_id)
        return _result(game_id, _reply(game_id))
    return _guard(run)


def _to_uci(game: Game, move: str) -> str:
    s = move.strip()
    if _UCI.match(s):
        return s
    board = game.board()
    try:
        return board.parse_san(s.replace("0-0-0", "O-O-O").replace("0-0", "O-O")).uci()
    except ValueError as e:  # illegal, ambiguous or unreadable: python-chess says which, we only say it is not playable
        raise Refused(f"{s} is not a legal move here. Use game_show to see the board and the legal moves.") from e


def game_move(game_id: str, move: str, expected_revision: int | None = None, reply: bool = True):
    """Play the player's move; with `reply` (the default, for text-only clients) Stockfish answers in the same call. The board page
    uses reply=False and then `game_engine_move`, so the player's move shows before the reply."""
    def run():
        game = _own(game_id)
        with game.lock:  # read the revision and the move's meaning against the same position
            uci = _to_uci(game, move)
            revision = game.revision if expected_revision is None else expected_revision
        T.apply_move(game_id, uci, revision, engine_reply_=False)  # the move is saved first; the reply is separate
        return _result(game_id, _reply(game_id) if reply else "", judge=reply)
    return _guard(run)


def game_engine_move(game_id: str, expected_revision: int):
    """Stockfish's reply to a move made with reply=False. Plays only if it is the engine's turn *and* the game is still at
    `expected_revision` (the position the page is showing), so a stale or double call never plays a second move."""
    def run():
        game = _own(game_id)
        if game.revision != expected_revision:
            raise GameError("revision_conflict", "")
        return _result(game_id, _reply(game_id))
    return _guard(run)


def game_judge(game_id: str, expected_revision: int):
    """The verdict on the player's move just shown, with no engine reply (the board asks for the reply separately), so the verdict
    can appear as soon as its search ends. Practice only has a verdict: in Play this returns the plain state. Idempotent, and the
    search is cached for `game_engine_move`, which then does not search twice."""
    def run():
        game = _own(game_id)
        if game.revision != expected_revision:
            raise GameError("revision_conflict", "")
        return _result(game_id)
    return _guard(run)


def game_resign(game_id: str):
    def run():
        _own(game_id)
        T.resign_game(game_id)
        return _result(game_id)
    return _guard(run)


def game_undo(game_id: str):
    def run():
        _own(game_id)
        T.take_back_move(game_id)
        return _result(game_id, "Your last move was taken back.")
    return _guard(run)


def game_hint(game_id: str, level: int = 1):
    def run():
        _own(game_id)
        h = T.hint(game_id, max(1, min(int(level), 5)))
        words = " ".join(f"{s['level']}. {s['text']}" for s in h["steps"])
        return _result(game_id, f"Hint: {words}", hint=h)
    return _guard(run)


def game_threats(game_id: str, show: bool = True):
    def run():
        game = _own(game_id)
        if game.mode is not Mode.PRACTICE:
            raise GameError("feedback_not_allowed", "")
        with _lock:
            _OWNED[game_id]["show_threats"] = bool(show)
        return _result(game_id, "Threat arrows are on." if show else "Threat arrows are off.")
    return _guard(run)
