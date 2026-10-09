"""The verifier (T18, spec H1): check every claim the coach makes against the rules, the engine and the detectors.

The coach LLM returns prose plus a list of atomic claims. Nothing is shown unless the claims pass (the harness gets one
repair attempt, then falls back to verified facts only). Claims are structured JSON objects; each has a `type`:

- move_legal      {move}                          the move is legal in the position
- line_legal      {moves: [...]}                  the moves can be played one after another
- move_captures   {move}                          the (legal) move captures a piece
- best_move       {move}                          the engine's first choice, or within BEST_WITHIN_CP of it
- piece_can_be_taken {square, side}               `side` ("user"/"opponent") owns a piece on `square` that the other side
                                                  can win by a legal capture (the hanging_own v2 definition)
- free_piece_available {square}                   the side to move can win the opponent's piece on `square`
                                                  (the missed_free v2 definition)
- eval_band       {band}                          the engine evaluation, from the user's side, is in the band
- mate_in         {side, moves}                   `side` mates within `moves` moves (engine mate score)

Every claim may add `position`: "before" (the position the user faced, default) or "after" (after the move played).
Moves are SAN or UCI. An unknown claim type fails: the verifier never assumes.

`check_assertions` is the third guard: tactical words in the text (checkmate, "free", "can be taken", "winning"...) must be
backed by a verified claim of the matching kind, or by a fact the harness itself computed. The vocabulary is a fixed list,
so it is a net with holes, not a proof; the E2 eval measures what still gets through.

`check_sequences` is the fourth guard (v2): when one sentence names two or more moves and reads like a line of play
("then", "follows", "reply", "the line goes"...), those moves must appear in that order and next to each other in a verified
`line_legal` claim or in an engine line the harness computed. Each move being legal on its own is not enough.

`check_prose` is the second guard: the text itself may only name moves and pawn amounts that the verified evidence
supports, so a claim cannot be smuggled in outside the claim list. Limit: bare squares ("e4") and pawn pushes written
as a square are not treated as moves; the prompt asks for "pawn to e4" wording, which is never checked as a move.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import chess

from app.detectors import hanging_own, missed_free
from app.engine.stockfish import Budget
from app.learner.review import cp_equiv

VERIFIER_BUDGET = Budget(depth=12)
BEST_WITHIN_CP = 30
BANDS = {  # user's side, centipawns (mates clamp to +/-1000)
    "winning": (200, 10_000),
    "better": (50, 200),
    "equal": (-50, 50),
    "worse": (-200, -50),
    "losing": (-10_000, -200),
}
VERSION = "2"  # v2: move sequences in the text must be backed by a legal-line claim or an engine line


@dataclass(frozen=True)
class Context:
    """The position under discussion."""

    fen: str  # the position the user faced
    user_color: chess.Color
    played_uci: str | None = None  # the move the user played, for "after" claims

    def board(self, position: str = "before") -> chess.Board:
        board = chess.Board(self.fen)
        if position == "after":
            if self.played_uci is None:
                raise ValueError("no played move for an 'after' claim")
            board.push_uci(self.played_uci)
        elif position != "before":
            raise ValueError(f"unknown position {position!r}")
        return board


@dataclass
class Report:
    verified: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)  # {claim, reason}
    prose_problems: list[str] = field(default_factory=list)
    version: str = VERSION

    @property
    def ok(self) -> bool:
        return not self.failed and not self.prose_problems


def _parse(board: chess.Board, text: str) -> chess.Move:
    for parse in (board.parse_san, board.parse_uci):
        try:
            move = parse(text)
        except ValueError:
            continue
        if move in board.legal_moves:
            return move
    raise ValueError(f"{text!r} is not a legal move here")


def _square(name) -> chess.Square:
    try:
        return chess.parse_square(name)
    except (ValueError, TypeError):
        raise ValueError(f"{name!r} is not a square") from None


class Verifier:
    def __init__(self, engine, ctx: Context, budget: Budget = VERIFIER_BUDGET):
        self.engine, self.ctx, self.budget = engine, ctx, budget
        self._cache: dict[str, object] = {}

    def _analyse(self, board: chess.Board, perspective: chess.Color | None = None):
        perspective = self.ctx.user_color if perspective is None else perspective
        key = (board.fen(), perspective)
        if key not in self._cache:
            self._cache[key] = self.engine.analyse(board, self.budget, perspective=perspective)
        return self._cache[key]

    def _cp(self, board: chess.Board, perspective: chess.Color | None = None) -> int:
        s = self._analyse(board, perspective).score
        return cp_equiv(s.cp, s.mate, s.mate_sign)

    def check(self, claim: dict) -> None:
        """Raise ValueError (with the reason) if the claim does not hold."""
        kind = claim.get("type")
        method = getattr(self, f"_check_{kind}", None) if isinstance(kind, str) else None
        if method is None:
            raise ValueError(f"unknown claim type {kind!r}")
        method(claim, self.ctx.board(claim.get("position", "before")))

    # -- claim types --------------------------------------------------------------------------
    def _check_move_legal(self, c, board):
        _parse(board, str(c.get("move")))

    def _check_line_legal(self, c, board):
        moves = c.get("moves")
        if not isinstance(moves, list) or not moves:
            raise ValueError("a line needs a list of moves")
        board = board.copy()
        for text in moves:
            board.push(_parse(board, str(text)))

    def _check_move_captures(self, c, board):
        move = _parse(board, str(c.get("move")))
        if not board.is_capture(move):
            raise ValueError(f"{c.get('move')} does not capture anything")

    def _check_best_move(self, c, board):
        move = _parse(board, str(c.get("move")))
        mover = board.turn
        best = self._analyse(board, mover)
        if best.best_move == move.uci():
            return
        after = board.copy()
        after.push(move)
        loss = self._cp(board, mover) - self._cp(after, mover)
        if loss > BEST_WITHIN_CP:
            raise ValueError(f"{c.get('move')} is not the engine's choice (it gives up {loss} centipawns)")

    def _check_piece_can_be_taken(self, c, board):
        owner = self._side(c)
        sq = chess.square_name(_square(c.get("square")))
        if sq not in {h.square for h in hanging_own.hanging_pieces(board, owner)}:
            raise ValueError(f"no piece on {sq} can be won by a legal capture")

    def _check_free_piece_available(self, c, board):
        sq = chess.square_name(_square(c.get("square")))
        if sq not in {h.square for h in missed_free.free_pieces(board)}:
            raise ValueError(f"no free piece on {sq} for the side to move")

    def _check_eval_band(self, c, board):
        band = c.get("band")
        if not isinstance(band, str) or band not in BANDS:
            raise ValueError(f"unknown band {band!r}")
        lo, hi = BANDS[band]
        cp = self._cp(board)
        if not lo <= cp < hi:
            raise ValueError(f"the engine puts the position at {cp / 100:+.1f} for the user, not '{band}'")

    def _check_mate_in(self, c, board):
        want_sign = 1 if self._side(c) == self.ctx.user_color else -1
        s = self._analyse(board).score
        n = c.get("moves")
        if s.mate is None or s.mate_sign != want_sign or not isinstance(n, int) or abs(s.mate) > n:
            raise ValueError("the engine does not find that mate")

    def _side(self, c) -> chess.Color:
        side = c.get("side")
        if side not in ("user", "opponent"):
            raise ValueError("side must be 'user' or 'opponent'")
        return self.ctx.user_color if side == "user" else not self.ctx.user_color


# ---- prose guard ------------------------------------------------------------------------------
_MOVE = re.compile(
    r"(?<![A-Za-z0-9])(O-O-O|O-O|[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?|[a-h]x[a-h][1-8](?:=[QRBN])?[+#]?|"
    r"[a-h][18]=[QRBN][+#]?)(?![A-Za-z0-9])"
)
_PAWNS = re.compile(r"(\d+(?:\.\d+)?)\s*pawns?\b")


def _norm(san: str) -> str:
    return san.rstrip("+#")


def check_prose(text: str, allowed_moves: set[str], allowed_pawns: set[float]) -> list[str]:
    """Problems in `text`: a named move, or a pawn amount, that no verified evidence supports."""
    allowed = {_norm(m) for m in allowed_moves}
    problems = []
    for m in _MOVE.findall(text):
        if _norm(m) not in allowed:
            problems.append(f"the text names the move {m}, which is not part of the verified evidence")
    for n in _PAWNS.findall(text):
        if not any(abs(float(n) - a) <= 0.15 for a in allowed_pawns):
            problems.append(f"the text says {n} pawns, which the engine did not report")
    return problems


ASSERTIONS = {  # category -> (words in the text, claim types that can back it)
    "mate": (
        re.compile(r"\b(check\s?mates?d?|mated|mating|mate)\b", re.IGNORECASE),
        {"mate_in"},
    ),
    "material": (
        re.compile(
            r"\b(free|hanging|unprotected|undefended|unguarded|loose|for nothing|can be (?:taken|captured|won)|"
            r"(?:wins?|won|winning|lose|loses|lost) (?:a|an|the|your|their|his|her|material)\b|captures?|takes? (?:the|a|your))",
            re.IGNORECASE),
        {"piece_can_be_taken", "free_piece_available", "move_captures"},
    ),
    "evaluation": (
        re.compile(r"\b(winning|losing|lost position|equal position|completely won|totally lost)\b", re.IGNORECASE),
        {"eval_band", "mate_in"},
    ),
}


def assertion_categories(text: str) -> set[str]:
    """Which kinds of tactical assertion the text makes."""
    return {name for name, (pattern, _) in ASSERTIONS.items() if pattern.search(text)}


def check_assertions(text: str, verified: list[dict], known: set[str] = frozenset()) -> list[str]:
    """Problems: an assertion in `text` that no verified claim (or harness-computed fact in `known`) supports."""
    have = {c.get("type") for c in verified}
    problems = []
    for name in sorted(assertion_categories(text)):
        if name in known or have & ASSERTIONS[name][1]:
            continue
        problems.append(f"the text makes a {name} statement that no verified claim supports")
    return problems


_CUE = re.compile(
    r"\b(then|next|follow(?:s|ed|ing)?|repl(?:y|ies|ied)|respond(?:s|ed)?|line|variation|sequence|after that|"
    r"afterwards|continu(?:e|es|ed)|plays?|played|answer(?:s|ed)?)\b",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _contiguous(needle: list[str], haystack: list[str]) -> bool:
    n = len(needle)
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def check_sequences(text: str, verified: list[dict], known_lines=()) -> list[str]:
    """Problems: a sentence that names two or more moves as a line of play that no verified line backs."""
    lines = [[_norm(m) for m in c.get("moves", []) if isinstance(m, str)]
             for c in verified if c.get("type") == "line_legal" and isinstance(c.get("moves"), list)]
    lines += [[_norm(m) for m in ln] for ln in known_lines]
    problems = []
    for sentence in _SENTENCE.split(text):
        tokens = [_norm(m) for m in _MOVE.findall(sentence)]
        if len(tokens) < 2 or not _CUE.search(sentence):
            continue
        if not any(_contiguous(tokens, ln) for ln in lines):
            problems.append("the text gives the moves " + " ".join(tokens) +
                            " as a line of play, which no verified line backs in that order")
    return problems


def moves_in(claim: dict) -> list[str]:
    """Moves a (verified) claim names, as written."""
    out = []
    if isinstance(claim.get("move"), str):
        out.append(claim["move"])
    if isinstance(claim.get("moves"), list):
        out += [m for m in claim["moves"] if isinstance(m, str)]
    return out


def verify(engine, ctx: Context, claims: list[dict], prose: str = "", known_moves=(), known_pawns=(),
           known_assertions: set[str] = frozenset(), known_lines=()) -> Report:
    """Check all claims, then the prose against what was verified (plus `known_moves`/`known_pawns`/`known_assertions`
    the harness itself computed, such as the played move, the engine's best move, what its detectors found and the
    engine's lines in SAN as `known_lines`)."""
    v = Verifier(engine, ctx)
    report = Report()
    for claim in claims:
        if not isinstance(claim, dict):
            report.failed.append({"claim": claim, "reason": "a claim must be an object"})
            continue
        try:
            v.check(claim)
            report.verified.append(claim)
        except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError) as e:
            report.failed.append({"claim": claim, "reason": str(e)})
        except (TypeError, AttributeError, KeyError) as e:  # a field of the wrong shape, e.g. a list where a word belongs
            report.failed.append({"claim": claim, "reason": f"malformed claim ({type(e).__name__}: {e})"})
    allowed = set(known_moves)
    for claim in report.verified:
        allowed.update(moves_in(claim))
    if prose:
        report.prose_problems += check_prose(prose, allowed, set(known_pawns))
        report.prose_problems += check_assertions(prose, report.verified, set(known_assertions))
        report.prose_problems += check_sequences(prose, report.verified, known_lines)
    return report
