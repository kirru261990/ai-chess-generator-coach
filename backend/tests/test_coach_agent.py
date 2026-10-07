import json

import chess
import pytest

from app.coach import agent
from app.coach.llm import CoachUnavailable, Draft
from tests.test_verifier import FREE_KNIGHT, FakeEngine

PLAYED = "e1f1"  # ignores the free knight


def engine():
    b = chess.Board(FREE_KNIGHT)
    b.push_uci(PLAYED)
    return FakeEngine(cp={FREE_KNIGHT: 300, b.fen(): 100}, best={FREE_KNIGHT: "d1d5"})


class Script:
    """A drafter that returns scripted replies and records what it was sent."""

    model = "scripted"

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def draft(self, system, messages):
        self.calls.append([dict(m) for m in messages])
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return Draft(reply, "scripted", 10, 20)


def reply(text, claims):
    return json.dumps({"explanation": text, "claims": claims})


GOOD = reply(
    "A free knight on d5 was there, and Rxd5 would have taken it. You left it, which cost about 2.0 pawns.",
    [{"type": "free_piece_available", "square": "d5"}, {"type": "move_legal", "move": "Rxd5"}],
)


def run(drafter):
    return agent.explain_move(engine(), drafter, FREE_KNIGHT, chess.WHITE, PLAYED)


def test_a_verified_draft_is_returned_as_is_with_its_versions():
    d = Script(GOOD)
    r = run(d)
    assert r["status"] == "verified" and r["text"].startswith("A free knight on d5")
    assert len(r["claims"]) == 2 and len(d.calls) == 1
    assert r["versions"]["prompt"] == "why_v1" and r["versions"]["model"] == "scripted"
    assert r["versions"]["engine"]["budget"] == {"depth": 12, "movetime_ms": None}
    assert "_feedback" not in r["evidence"]


def test_the_model_only_sees_the_evidence_pack_not_a_free_form_question():
    d = Script(GOOD)
    run(d)
    sent = d.calls[0][0]["content"]
    assert "Evidence" in sent and "d1d5" in sent and "Rxd5" in sent


def test_a_failed_claim_gets_one_repair_with_the_reasons():
    bad = reply("Qh5 wins at once.", [{"type": "move_legal", "move": "Qh5"}])
    d = Script(bad, GOOD)
    r = run(d)
    assert r["status"] == "repaired" and len(d.calls) == 2
    assert "Verification failed" in d.calls[1][-1]["content"] and "Qh5" in d.calls[1][-1]["content"]
    assert [a["ok"] for a in r["attempts"]] == [False, True]


def test_two_failures_fall_back_to_verified_facts_with_a_note():
    bad = reply("Qh5 wins at once.", [{"type": "move_legal", "move": "Qh5"}])
    r = run(Script(bad, bad))
    assert r["status"] == "fallback" and r["note"] == agent.NOTE_FALLBACK and r["claims"] == []
    assert "Qh5" not in r["text"] and "free knight on d5" in r["text"]


def test_a_move_in_the_prose_that_no_claim_supports_is_rejected():
    sneaky = reply("Rxd5 wins, and Rd8+ then mates.", [{"type": "move_legal", "move": "Rxd5"}])
    r = run(Script(sneaky, GOOD))
    assert r["status"] == "repaired" and "Rd8+" in r["attempts"][0]["problems"][0]


def test_an_invented_pawn_amount_is_rejected():
    wrong = reply("Rxd5 was better. You lost 7 pawns.", [{"type": "move_legal", "move": "Rxd5"}])
    assert run(Script(wrong, GOOD))["status"] == "repaired"


def test_unreadable_replies_count_as_failures():
    assert run(Script("sorry, no JSON", "{not json"))["status"] == "fallback"
    assert run(Script('{"explanation": "", "claims": []}', GOOD))["status"] == "repaired"


def test_without_a_model_the_facts_are_returned_not_an_error():
    for drafter in (None, Script(CoachUnavailable("no key"))):
        r = run(drafter)
        assert r["status"] == "unavailable" and r["note"] == agent.NOTE_UNAVAILABLE
        assert "free knight on d5" in r["text"]


def test_illegal_move_input_is_refused_before_any_model_call():
    d = Script(GOOD)
    with pytest.raises(ValueError):
        agent.explain_move(engine(), d, FREE_KNIGHT, chess.WHITE, "a1a8")
    assert d.calls == []


def test_only_the_why_intent_is_supported():
    assert agent.classify_intent(None) == "why_move" and agent.classify_intent("Why was that bad?") == "why_move"
    with pytest.raises(ValueError):
        agent.classify_intent("what is the capital of France")


def test_pawn_moves_and_squares_in_prose_are_not_mistaken_for_moves():
    ok = reply("Put the pawn to e4 and keep the king on e1; the knight on d5 is free.",
               [{"type": "free_piece_available", "square": "d5"}])
    assert run(Script(ok))["status"] == "verified"


def test_a_tactical_statement_without_a_matching_claim_gets_repaired():
    unsupported = reply("Your opponent is checkmated after Rxd5.", [{"type": "move_legal", "move": "Rxd5"}])
    r = run(Script(unsupported, GOOD))
    assert r["status"] == "repaired" and "mate statement" in r["attempts"][0]["problems"][0]


def test_statements_the_engine_evidence_already_makes_need_no_extra_claim():
    # The detector evidence says a free piece was left ("right"/"wrong" lines), so the harness knows that kind of
    # statement is supported; the moves and amounts are still checked.
    ok = reply("You left a free piece. Rxd5 was available.", [{"type": "move_legal", "move": "Rxd5"}])
    assert run(Script(ok))["status"] == "verified"
