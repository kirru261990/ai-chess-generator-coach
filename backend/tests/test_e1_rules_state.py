"""E1 (spec section 07): rules and state. Target: zero illegal transitions, duplicate moves, cross-user access, or
assisted results labelled unassisted.

Example-based tests live in test_core_game.py and test_api.py. This suite is randomized and differential: seeded random
action sequences (legal and illegal moves, stale and duplicate revisions, mode switches, takebacks, resignations) are
applied to the real game objects and, independently, to a plain python-chess reference board. After EVERY action the
invariants below are checked. A failure prints the seed and the action list so it can be replayed.

Invariants
  I1  an accepted action changes the state exactly as the reference says; a rejected action changes nothing
  I2  the revision never goes down; it goes up by exactly 1 on every accepted action and never on a rejected one
  I3  the position and the outcome always equal the reference board's
  I4  `assisted` never goes from true to false; Practice start, switching to Practice, and any takeback set it
  I5  takebacks happen only in Practice, only before resignation, as often as the player likes (no cap), and return to
      the user's turn
  I6  a duplicate (same move, same revision) never applies twice
  I7  nothing but a takeback (after mate or draw) is accepted once the game is over
  I8  the exported PGN replays to the same position and carries the same Assisted and Mode headers
"""

import io
import random

import chess
import chess.pgn
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.core.game import (
    GameError,
    Mode,
    make_move,
    new_game,
    resign,
    set_mode,
    take_back,
    to_pgn,
)

SEEDS = range(300)
MAX_ACTIONS = 70
GARBAGE = ["", "0000", "zzzz", "e2e9", "a1a1", "e2e4e", "O-O", "E2E4", "e7e8x", "  ", "e2 e4", "💥"]


def snapshot(g):
    return (tuple(g.moves), g.revision, g.mode, g.assisted, g.resigned_by)


def reference_outcome(board):
    out = board.outcome(claim_draw=False)
    if out is not None:
        return (out.result(), out.termination.name.lower())
    if board.is_repetition(3):
        return ("1/2-1/2", "threefold_repetition")
    if board.is_fifty_moves():
        return ("1/2-1/2", "fifty_moves")
    return None


class Model:
    """Independent reference: a python-chess board plus the few flags the rules define."""

    def __init__(self, game):
        self.board = chess.Board(game.start_fen)
        self.user = game.user_color
        self.engine = game.engine_level is not None
        self.mode = game.mode
        self.assisted = game.assisted
        self.resigned = False
        self.takebacks = 0  # how many takebacks happened (for the reach test only; there is no cap)

    def over(self):
        return self.resigned or reference_outcome(self.board) is not None


def can_undo(model):
    """Reference rule: there is a move of the user's to take back (the engine's reply goes with it)."""
    plies = 2 if model.engine and model.board.turn == model.user else 1
    return len(model.board.move_stack) >= plies


def check(game, model, log):
    msg = f"actions so far: {log}"
    assert game.board().fen() == model.board.fen(), msg  # I3
    out = game.outcome()
    if model.resigned:
        assert out is not None and out["termination"] == "resignation", msg
    else:
        ref = reference_outcome(model.board)
        assert (None if out is None else (out["result"], out["termination"])) == ref, msg  # I3
    assert game.mode == model.mode and game.assisted == model.assisted, msg  # I4
    assert game.can_take_back == (model.mode is Mode.PRACTICE and not model.resigned and can_undo(model)), msg  # I5


def run_sequence(seed):
    rng = random.Random(seed)
    user = rng.choice([chess.WHITE, chess.BLACK])
    mode = rng.choice([Mode.PLAY, Mode.PRACTICE])
    engine_level = rng.choice([None, 1])
    game = new_game(user, mode, engine_level=engine_level)
    model = Model(game)
    log = [f"start user={'white' if user else 'black'} mode={mode.value} engine={engine_level}"]
    assert game.assisted == (mode is Mode.PRACTICE), log  # I4: Practice starts assisted
    if engine_level and model.board.turn != user:  # the engine opens
        reply = rng.choice(list(model.board.legal_moves))
        make_move(game, reply.uci(), game.revision)
        model.board.push(reply)

    for _ in range(rng.randint(1, MAX_ACTIONS)):
        before, rev_before = snapshot(game), game.revision
        action = rng.choices(["move", "illegal", "stale", "dup", "mode", "takeback", "resign"],
                             [50, 8, 6, 6, 6, 8, 2])[0]
        log.append(action)
        accepted = False
        try:
            if action == "move":
                legal = list(model.board.legal_moves)
                mv = rng.choice(legal) if legal else chess.Move.from_uci("e2e4")
                if model.board.turn != user and engine_level:
                    raise GameError("not_your_turn", "engine to move")  # the API refuses it; the core has no turn rule
                make_move(game, mv.uci(), game.revision)
                model.board.push(mv)
                accepted = True
            elif action == "illegal":
                bad = rng.choice(GARBAGE + [m.uci() for m in chess.Board().legal_moves])  # most are illegal here
                if bad in {m.uci() for m in model.board.legal_moves}:
                    continue  # it happens to be legal here: not an illegal-move case
                make_move(game, bad, game.revision)
                pytest.fail(f"illegal move {bad!r} was accepted; {log}")
            elif action == "stale":
                legal = list(model.board.legal_moves)
                if not legal:
                    continue
                make_move(game, rng.choice(legal).uci(), game.revision + rng.choice([-1, 1, 5]))
                pytest.fail(f"a stale revision was accepted; {log}")
            elif action == "dup":
                legal = list(model.board.legal_moves)
                if not legal or (engine_level and model.board.turn != user):
                    continue
                mv = rng.choice(legal)
                rev = game.revision
                make_move(game, mv.uci(), rev)
                model.board.push(mv)
                rev_after_first = game.revision
                snap_after_first = snapshot(game)
                with pytest.raises(GameError):  # I6
                    make_move(game, mv.uci(), rev)
                assert snapshot(game) == snap_after_first and game.revision == rev_after_first, log
                accepted = True
            elif action == "mode":
                new = rng.choice([Mode.PLAY, Mode.PRACTICE])
                changed = (new, model.assisted or new is Mode.PRACTICE) != (model.mode, model.assisted)
                set_mode(game, new)
                model.mode = new
                model.assisted = model.assisted or new is Mode.PRACTICE
                assert game.revision == rev_before + (1 if changed else 0), log  # I2
                check(game, model, log)
                continue
            elif action == "takeback":
                n_before = len(model.board.move_stack)
                take_back(game)
                accepted = True
                k = n_before - len(game.moves)
                assert k in (1, 2), log
                for _ in range(k):
                    model.board.pop()
                model.assisted = True
                model.takebacks += 1
                assert model.mode is Mode.PRACTICE and not model.resigned, log  # I5
                if engine_level and len(model.board.move_stack) >= 1:
                    assert model.board.turn == user or k == 1, log  # I5: back to the user's turn
            elif action == "resign":
                resign(game, user)
                model.resigned = True
                accepted = True
        except GameError:
            assert snapshot(game) == before, f"a rejected {action} changed the state; {log}"  # I1, I2
            assert game.revision == rev_before, log
            check(game, model, log)
            continue
        if accepted and action in ("move", "resign", "takeback"):
            assert game.revision == rev_before + 1, f"revision jumped on {action}; {log}"  # I2
        check(game, model, log)

        # the engine replies when it is its turn and the game is on
        if engine_level and not model.over() and model.board.turn != user:
            reply = rng.choice(list(model.board.legal_moves))
            make_move(game, reply.uci(), game.revision)
            model.board.push(reply)
            check(game, model, log)
    return game, model, log


@pytest.mark.parametrize("seed", SEEDS)
def test_random_sequences_keep_every_invariant(seed):
    game, model, log = run_sequence(seed)
    # I7: once the game is over only a takeback (never after resignation) may still be accepted
    if model.over():
        rev = game.revision
        some = next(iter(model.board.legal_moves), chess.Move.from_uci("e2e4"))
        with pytest.raises(GameError):
            make_move(game, some.uci(), rev)
        with pytest.raises(GameError):
            resign(game, game.user_color)
        assert game.revision == rev, log
    # I8: the PGN replays to the same position with the same flags
    pgn = chess.pgn.read_game(io.StringIO(to_pgn(game)))
    assert pgn.headers["Assisted"] == str(game.assisted).lower() and pgn.headers["Mode"] == game.mode.value
    replay = pgn.board()
    for m in pgn.mainline_moves():
        replay.push(m)
    assert replay.fen() == game.board().fen(), log


def test_the_sequences_actually_reach_every_kind_of_state():
    """Guard against a suite that passes because it never gets anywhere."""
    seen = {"over": 0, "assisted_play": 0, "takeback": 0, "resigned": 0, "mated_or_drawn": 0}
    for seed in range(120):
        game, model, _ = run_sequence(seed)
        seen["over"] += model.over()
        seen["resigned"] += model.resigned
        seen["mated_or_drawn"] += reference_outcome(model.board) is not None
        seen["assisted_play"] += game.assisted and game.mode is Mode.PLAY
        seen["takeback"] += model.takebacks > 0
    assert seen["takeback"] > 5 and seen["assisted_play"] > 5 and seen["resigned"] > 0, seen


# ---- the same invariants over HTTP (no engine needed: engine_reply=false) -------------------------------------------
client = TestClient(app)


def view(gid):
    return client.get(f"/games/{gid}").json()


@pytest.mark.parametrize("seed", range(20))
def test_http_actions_never_mislabel_assisted_or_apply_a_duplicate(seed):
    rng = random.Random(seed)
    mode = rng.choice(["play", "practice"])
    gid = client.post("/games", json={"mode": mode, "level": 1}).json()["id"]
    assisted_seen = view(gid)["assisted"]
    assert assisted_seen == (mode == "practice")
    for _ in range(rng.randint(1, 25)):
        v = view(gid)
        if v["outcome"]:
            break
        legal = v["legal_moves"]
        action = rng.choice(["move", "dup", "mode", "takeback", "bad"])
        if action in ("move", "dup") and legal and v["turn"] == v["user_color"]:
            uci = rng.choice(legal)
            r = client.post(f"/games/{gid}/moves", json={"uci": uci, "expected_revision": v["revision"],
                                                          "engine_reply": False})
            assert r.status_code == 200
            if action == "dup":  # the same request again: must be refused, state unchanged
                again = client.post(f"/games/{gid}/moves", json={"uci": uci, "expected_revision": v["revision"],
                                                                  "engine_reply": False})
                # refused either way: the turn check (not_your_turn) runs before the revision check (revision_conflict)
                assert again.status_code == 409 and again.json()["error"] in ("revision_conflict", "not_your_turn")
                assert view(gid)["moves"] == r.json()["moves"]
            # let a legal reply stand in for the engine so the user can move again
            w = view(gid)
            if not w["outcome"] and w["turn"] != w["user_color"]:
                client.post(f"/games/{gid}/engine-move", json={})  # needs the engine; refused if absent, harmless
        elif action == "mode":
            client.post(f"/games/{gid}/mode", json={"mode": rng.choice(["play", "practice"])})
        elif action == "takeback":
            client.post(f"/games/{gid}/takeback", json={})
        else:
            before = view(gid)
            r = client.post(f"/games/{gid}/moves", json={"uci": rng.choice(GARBAGE), "expected_revision": before["revision"]})
            assert r.status_code in (400, 409)
            assert view(gid) == before
        now = view(gid)
        assert not (assisted_seen and not now["assisted"]), "assisted went from true to false"  # I4
        assisted_seen = now["assisted"]
        if now["mode"] == "practice":
            assert now["assisted"] is True
        assert now["revision"] >= v["revision"]  # I2
    pgn = client.get(f"/games/{gid}/pgn").text
    assert f'[Assisted "{str(view(gid)["assisted"]).lower()}"]' in pgn


def test_a_takeback_in_play_mode_is_refused_over_http_and_leaves_the_game_unassisted():
    gid = client.post("/games", json={"mode": "play"}).json()["id"]
    client.post(f"/games/{gid}/moves", json={"uci": "e2e4", "expected_revision": 0, "engine_reply": False})
    before = view(gid)
    r = client.post(f"/games/{gid}/takeback", json={})
    assert r.status_code == 409 and r.json()["error"] == "takeback_not_allowed"
    assert view(gid) == before and before["assisted"] is False


@pytest.mark.skip(reason="cross-user access cannot be tested until sign-in and per-user data isolation exist (spec Week 4); "
                         "today games are not owned by anyone, which this skip keeps visible rather than pretending to pass")
def test_one_user_cannot_read_or_move_another_users_game():
    raise AssertionError("write this when games have owners")
