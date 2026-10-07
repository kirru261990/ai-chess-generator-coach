"""The coach agent harness (T17, spec H1): intent -> exact state -> tools -> draft -> verify -> respond.

One intent is supported so far: `why_move`, "why was this move good or bad?" for a move the user played.

1. State: the position and the move come from the backend (the LLM never supplies them).
2. Tools: the engine and detectors produce an evidence pack (`learner.feedback.judge` plus the engine's lines in SAN).
3. Draft: the coach model gets only the evidence pack and must return prose plus checkable claims.
4. Verify: every claim and every move or pawn amount in the prose is checked (`coach.verifier`).
5. Respond: verified text; if it fails, ONE repair attempt with the failures; if that fails too (or no model is
   available), only the verified facts plus an uncertainty note (rule 2).
Everything is versioned in the result: prompt, model, verifier, detectors, engine budget (rule 6).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import chess

from app.coach import verifier
from app.coach.llm import CoachUnavailable, Draft, Drafter
from app.learner.feedback import analyse_move, judge

PROMPT_VERSION = "why_v1"
PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT = (PROMPTS_DIR / f"{PROMPT_VERSION}.md").read_text()
LINE_PLIES = 6
INTENTS = ("why_move",)
NOTE_FALLBACK = (
    "I could not fully check a longer explanation, so this is limited to facts the engine and rules confirmed."
)
NOTE_UNAVAILABLE = "The coach model is not available right now, so this is limited to facts the engine confirmed."


def classify_intent(text: str | None) -> str:
    """Only one intent exists so far. Anything else is refused rather than guessed (rule: abstain)."""
    if text is None or re.search(r"\bwhy\b", text, re.IGNORECASE):
        return "why_move"
    raise ValueError("I can only explain why a move was good or bad so far.")


def _san_line(board: chess.Board, ucis, limit: int = LINE_PLIES) -> list[str]:
    board = board.copy()
    out = []
    for u in list(ucis)[:limit]:
        move = chess.Move.from_uci(u)
        if move not in board.legal_moves:
            break
        out.append(board.san(move))
        board.push(move)
    return out


def build_evidence(engine, fen: str, user_color: chess.Color, played_uci: str) -> dict:
    board = chess.Board(fen)
    move = chess.Move.from_uci(played_uci)
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {played_uci} in {fen}")
    best, after = analyse_move(engine, board, move, user_color)
    fb = judge(board, move, best, after)
    after_board = board.copy()
    after_board.push(move)
    return {
        "position_fen": fen,
        "player_color": "white" if user_color == chess.WHITE else "black",
        "played": fb["played"],
        "better_move": fb["better_move"],
        "verdict": fb["verdict"],
        "headline": fb["headline"],
        "cost_pawns": fb["cost_pawns"],
        "right": fb["right"],
        "wrong": fb["wrong"],
        "best_line_from_position": _san_line(board, best.pv),
        "line_after_played_move": _san_line(after_board, after.pv),
        "_feedback": fb,
    }


def known_moves(evidence: dict) -> set[str]:
    moves = set(evidence["best_line_from_position"]) | set(evidence["line_after_played_move"])
    moves.add(evidence["played"]["text"].rsplit("(", 1)[-1].rstrip(")"))
    if evidence["better_move"]:
        moves.add(evidence["better_move"]["text"].rsplit("(", 1)[-1].rstrip(")"))
    return moves


def known_assertions(evidence: dict) -> set[str]:
    """Kinds of tactical statement the engine/detector evidence itself already makes (its right/wrong lines)."""
    return verifier.assertion_categories(" ".join(evidence["right"] + evidence["wrong"]))


def parse_draft(text: str) -> tuple[str, list]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    data = json.loads(text[start : end + 1])
    explanation, claims = data.get("explanation"), data.get("claims")
    if not isinstance(explanation, str) or not explanation.strip() or not isinstance(claims, list):
        raise ValueError("the reply needs an 'explanation' text and a 'claims' list")
    return explanation.strip(), claims


def facts_text(evidence: dict) -> str:
    """The deterministic explanation: only what the engine and detectors confirmed."""
    parts = [evidence["headline"], f"You played {evidence['played']['text']}."]
    parts += [f"✓ {t}" for t in evidence["right"]] + [f"✗ {t}" for t in evidence["wrong"]]
    if evidence["cost_pawns"]:
        parts.append(f"This cost about {evidence['cost_pawns']} pawns of advantage.")
    if evidence["better_move"]:
        parts.append(f"The engine preferred {evidence['better_move']['text']}.")
    return " ".join(parts)


def _user_message(evidence: dict) -> str:
    public = {k: v for k, v in evidence.items() if not k.startswith("_")}
    return "Evidence (computed by the engine and rules; use only this):\n" + json.dumps(public, indent=1)


def explain_move(engine, drafter: Drafter | None, fen: str, user_color: chess.Color, played_uci: str,
                 question: str | None = None, keep_drafts: bool = False) -> dict:
    """`keep_drafts` adds each attempt's unverified draft text to the result, for evals only; it is never returned
    by the API, so unchecked text cannot reach a player."""
    classify_intent(question)
    evidence = build_evidence(engine, fen, user_color, played_uci)
    fb = evidence["_feedback"]
    ctx = verifier.Context(fen, user_color, played_uci)
    pawns = {fb["cost_pawns"]} if fb["cost_pawns"] is not None else set()
    moves = known_moves(evidence)
    result = {
        "intent": "why_move",
        "evidence": {k: v for k, v in evidence.items() if not k.startswith("_")},
        "versions": {
            "prompt": PROMPT_VERSION,
            "model": getattr(drafter, "model", None),
            "verifier": verifier.VERSION,
            "engine": fb["evidence"],
        },
        "attempts": [],
    }

    def fallback(status: str, note: str) -> dict:
        return {**result, "status": status, "text": facts_text(evidence), "note": note, "claims": []}

    if drafter is None:
        return fallback("unavailable", NOTE_UNAVAILABLE)
    messages = [{"role": "user", "content": _user_message(evidence)}]
    for attempt in range(2):  # the first draft, then one repair
        try:
            draft: Draft = drafter.draft(PROMPT, messages)
        except CoachUnavailable as e:
            result["attempts"].append({"error": str(e)})
            return fallback("unavailable", NOTE_UNAVAILABLE)
        try:
            explanation, claims = parse_draft(draft.text)
            report = verifier.verify(engine, ctx, claims, explanation, moves, pawns, known_assertions(evidence))
            problems = [f"claim {json.dumps(f['claim'])}: {f['reason']}" for f in report.failed] + report.prose_problems
        except ValueError as e:  # not parseable
            explanation, claims, report, problems = "", [], None, [f"the reply could not be read: {e}"]
        record = {"ok": not problems, "problems": problems,
                  "tokens": {"input": draft.input_tokens, "output": draft.output_tokens}}
        if keep_drafts:
            record["draft"] = explanation
        result["attempts"].append(record)
        if not problems:
            status = "verified" if attempt == 0 else "repaired"
            return {**result, "status": status, "text": explanation, "claims": report.verified, "note": None}
        messages += [
            {"role": "assistant", "content": draft.text},
            {"role": "user", "content": "Verification failed:\n- " + "\n- ".join(problems)
             + "\nReturn the corrected JSON object. Claim only what the evidence supports."},
        ]
    return fallback("fallback", NOTE_FALLBACK)
