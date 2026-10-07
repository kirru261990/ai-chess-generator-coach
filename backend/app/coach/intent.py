"""'What were you considering?' (T19, spec D2, eval E4).

At a key moment the player may say what they were thinking. Their answer is stored as self-reported and is never
inferred or improved. The answer is compared with a fixed list of facts that were really on the board, built by the
detectors and the rules (`moment_facts`):

- a free piece the player could have taken (`missed_free`)
- a threat the opponent had against the player's pieces or king before the move (`threats`)
- a piece the player's move left to be taken (`hanging_own`)
- a checkmate the move missed or allowed (from the review's engine flags)

The coach model has ONE job: say which fact ids the answer mentions. It cannot write the comparison. The gap text is
assembled here from the facts, so a gap statement can only name something that is actually on the board and nothing
the player did not say is claimed about their intent. The answer is untrusted data (rule 7): the model can only return
ids from the list, so an injected instruction has no text channel to the player.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import chess

from app.coach.llm import CoachUnavailable, Drafter
from app.detectors import hanging_own, missed_free
from app.learner.feedback import PIECE
from app.learner.review import DEEP_BUDGET
from app.learner.threats import mate_threats

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_VERSION = "intent_v1"
MAX_ANSWER_CHARS = 500
MAX_GAPS = 2


def clean_answer(text: str | None) -> str:
    """The player's words, trimmed. Never altered otherwise."""
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text or "").strip()
    return text[:MAX_ANSWER_CHARS]


def mate_flags(engine, fen: str, user_color: chess.Color, played_uci: str) -> list[str]:
    """Engine-confirmed mates (deep search, same budget as the review): a forced mate the move missed, or one it allowed."""
    board = chess.Board(fen)
    best = engine.analyse(board, DEEP_BUDGET, perspective=user_color)
    board.push(chess.Move.from_uci(played_uci))
    after = engine.analyse(board, DEEP_BUDGET, perspective=user_color)
    flags = []
    if best.score.mate_sign == 1 and after.score.mate_sign != 1:
        flags.append("missed_mate")
    if after.score.mate_sign == -1 and best.score.mate_sign != -1:
        flags.append("allowed_mate")
    return flags


def moment_facts(fen: str, user_color: chess.Color, played_uci: str, flags: list[str] | None = None) -> list[dict]:
    """The checkable facts about this moment, each `{id, kind, text}`. Order is fixed so ids are stable."""
    board = chess.Board(fen)
    move = chess.Move.from_uci(played_uci)
    if move not in board.legal_moves or board.turn != user_color:
        raise ValueError("not a legal move for the player in this position")
    facts: list[dict] = []

    def add(kind: str, text: str):
        facts.append({"id": len(facts) + 1, "kind": kind, "text": text})

    for h in missed_free.free_pieces(board):
        add("free_piece", f"A free {PIECE[h.piece.lower()]} on {h.square} was there to take.")
    for h in hanging_own.hanging_pieces(board, user_color):
        add("threat_piece", f"Your opponent was threatening to win your {PIECE[h.piece.lower()]} on {h.square}.")
    for san in mate_threats(board):
        add("threat_mate", f"Your opponent was threatening checkmate with {san}.")
    after = board.copy()
    after.push(move)
    before_squares = {h.square for h in hanging_own.hanging_pieces(board, user_color)}
    for h in hanging_own.hanging_pieces(after, user_color):
        if h.square not in before_squares:  # a problem the move itself created
            add("left_hanging", f"After your move, your {PIECE[h.piece.lower()]} on {h.square} could be taken.")
    for flag in flags or []:
        if flag == "missed_mate":
            add("missed_mate", "There was a forced checkmate for you.")
        elif flag == "allowed_mate":
            add("allowed_mate", "Your move allowed a forced checkmate against you.")
    return facts


def _ids_from(text: str, valid: set[int]) -> tuple[list[int], list[str]]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    data = json.loads(text[start : end + 1])
    raw = data.get("mentioned")
    if not isinstance(raw, list):
        raise ValueError("the reply needs a 'mentioned' list")  # noqa: TRY004 - a bad reply is a ValueError here

    def good(i) -> bool:
        return isinstance(i, int) and not isinstance(i, bool) and i in valid

    return sorted({i for i in raw if good(i)}), [f"ignored id {i!r}" for i in raw if not good(i)]


def compare(drafter: Drafter | None, answer: str, facts: list[dict]) -> dict:
    """Which facts the answer mentions, and the gap text built from the rest."""
    result = {"status": "skipped", "mentioned": [], "gaps": [], "spotted": [], "model": getattr(drafter, "model", None),
              "prompt": PROMPT_VERSION, "ignored": []}
    if not answer:
        return result
    if not facts:
        return {**result, "status": "nothing_to_compare"}
    if drafter is None:
        return {**result, "status": "unavailable"}
    system = (PROMPTS_DIR / f"{PROMPT_VERSION}.md").read_text()
    listing = "\n".join(f"{f['id']}. {f['text']}" for f in facts)
    message = f"<answer>\n{answer}\n</answer>\n\nFacts:\n{listing}"
    valid = {f["id"] for f in facts}
    for _ in range(2):  # one retry if the reply cannot be read
        try:
            draft = drafter.draft(system, [{"role": "user", "content": message}])
        except CoachUnavailable:
            return {**result, "status": "unavailable"}
        try:
            ids, dropped = _ids_from(draft.text, valid)
        except ValueError:
            continue
        by_id = {f["id"]: f for f in facts}
        return {**result, "status": "compared", "mentioned": ids, "ignored": dropped,
                "spotted": [by_id[i]["text"] for i in ids],
                "gaps": [f["text"] for f in facts if f["id"] not in ids][:MAX_GAPS]}
    return {**result, "status": "unavailable"}
