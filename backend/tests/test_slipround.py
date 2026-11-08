"""First-slip drills and rounds (ADR 0020): the drill record, building a round, and what a round shows before the answer."""

import chess
import pytest

from app.learner import slipfinder as SF
from app.learner import slipround as SR

START = chess.Board().fen()


def slip(fen=START, played="e2e4", accepted=("d2d4", "g1f3"), loss=300):
    return {"ply": 8, "fen": fen, "side": "white", "played": played, "played_san": "e4", "loss_cp": loss,
            "accepted": [{"uci": u, "san": u, "cp": 0} for u in accepted], "versions": {"slip_finder": "1", "engine_config": "ec-x"}}


def test_a_slip_becomes_a_drill_with_a_stable_id_a_source_and_the_accepted_moves():
    d = SF.to_drill(slip(), game_id="g1", avg_rating=900, source="own")
    assert (d["type"], d["source"], d["game_id"], d["avg_rating"]) == ("S1", "own", "g1", 900)
    assert d["accepted"] == ["d2d4", "g1f3"] and d["fen"] == START
    assert d["id"] == SF.to_drill(slip(), game_id="g1", avg_rating=900, source="own")["id"]
    assert d["id"] != SF.to_drill(slip(played="d2d4"), game_id="g1", avg_rating=900, source="own")["id"]
    assert d["versions"]["slip_finder"] == "1"


def drills(n_own, n_fresh):
    out = []
    for i in range(n_own):
        out.append(SF.to_drill(slip(played=f"own{i}"), game_id=f"o{i}", avg_rating=800 + i, source="own"))
    for i in range(n_fresh):
        out.append(SF.to_drill(slip(played=f"fresh{i}"), game_id=f"f{i}", avg_rating=700 + i, source="lichess"))
    return out


def test_a_round_is_five_own_and_five_fresh_easiest_first_one_per_game():
    pool = drills(8, 8) + [SF.to_drill(slip(played="dup"), game_id="o0", avg_rating=100, source="own")]  # second drill from game o0
    r = SR.build_round(pool)
    assert [d["source"] for d in r].count("own") == 5 and [d["source"] for d in r].count("lichess") == 5
    assert len({d["game_id"] for d in r}) == 10
    assert [d["avg_rating"] for d in r if d["source"] == "own"] == sorted(d["avg_rating"] for d in r if d["source"] == "own")
    assert [d["played"] for d in r if d["game_id"] == "o0"] == ["dup"]  # the easier of the two drills from that game


def test_a_drill_used_in_an_earlier_round_is_not_offered_again():
    pool = drills(12, 12)
    first = SR.build_round(pool)
    second = SR.build_round(pool, exclude={d["id"] for d in first})
    assert not {d["id"] for d in first} & {d["id"] for d in second}


def test_a_short_source_is_topped_up_from_the_other_and_too_few_drills_is_an_error():
    r = SR.build_round(drills(8, 2))
    assert len(r) == 10 and [d["source"] for d in r].count("lichess") == 2
    with pytest.raises(SR.RoundError) as e:
        SR.build_round(drills(3, 2))
    assert e.value.code == "round_too_small"


# --- a round in progress: the ledger, answering, and the leak test ---------------------------------------------------------

import json

from fastapi.testclient import TestClient

from app.api.main import app
from app.learner import drillbank

client = TestClient(app)
FORBIDDEN = {"accepted", "evidence", "played", "played_san", "in_the_game", "matched", "checked_moves", "loss_cp", "source"}
SHOWN = {"done", "round", "position", "total", "drill_id", "fen", "side", "question", "legal_moves"}


def keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from keys(v)


@pytest.fixture
def slips(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    pool = []
    for i in range(12):
        for source in ("own", "lichess"):
            pool.append(SF.to_drill(slip(played=f"{source}{i}"), game_id=f"{source[0]}{i}", avg_rating=800 + i,
                                    source="own" if source == "own" else "lichess"))
    drillbank.bank_dir().mkdir(parents=True)
    SR.slips_path().write_text("".join(json.dumps(d) + "\n" for d in pool))
    return pool


@pytest.fixture
def conn(slips):
    c = SR.connect()
    yield c
    c.close()


def test_what_is_shown_before_the_answer_holds_only_the_board_the_side_the_question_and_the_legal_moves(slips, conn):
    shown = SR.current(conn)
    assert set(shown) == SHOWN
    assert not set(keys(shown)) & FORBIDDEN
    assert shown["position"] == 1 and shown["total"] == 10 and shown["side"] == "white"
    assert shown["legal_moves"] == sorted(m.uci() for m in chess.Board(START).legal_moves)


def test_a_match_is_one_of_the_accepted_moves_and_a_miss_is_not_called_wrong(slips, conn):
    shown = SR.current(conn)
    hit = SR.answer(conn, shown["drill_id"], "d2d4")
    assert hit["matched"] is True and hit["assisted"] is True and hit["in_the_game"] == "e4"
    nxt = SR.current(conn)
    miss = SR.answer(conn, nxt["drill_id"], "a2a3")
    assert miss["matched"] is False and "did not rule" in miss["not_checked"]
    assert "wrong" not in json.dumps(miss).lower()


def test_an_illegal_move_a_second_answer_and_a_position_not_on_screen_are_refused(slips, conn):
    shown = SR.current(conn)
    with pytest.raises(SR.RoundError) as e:
        SR.answer(conn, shown["drill_id"], "e2e5")
    assert e.value.code == "illegal_move"
    SR.answer(conn, shown["drill_id"], "d2d4")
    with pytest.raises(SR.RoundError) as e:
        SR.answer(conn, shown["drill_id"], "d2d4")
    assert e.value.code == "already_answered"
    with pytest.raises(SR.RoundError) as e:
        SR.answer(conn, "not-a-drill", "d2d4")
    assert e.value.code == "not_current_position"


def test_a_finished_round_is_summarised_and_the_next_round_uses_new_drills(slips, conn):
    first_ids = []
    for _ in range(10):
        shown = SR.current(conn)
        first_ids.append(shown["drill_id"])
        SR.answer(conn, shown["drill_id"], "d2d4")
    done = SR.current(conn)
    assert done["done"] is True and done["summary"]["matched"] == 10 and done["summary"]["answered"] == 10
    second = SR.current(conn)
    assert second["done"] is False and second["round"] == 2 and second["drill_id"] not in first_ids


def test_http_flow_keeps_the_leak_rule_and_a_missing_file_is_a_plain_409(slips):
    r = client.get("/drills/rounds/current")
    assert r.status_code == 200 and set(r.json()) == SHOWN and not set(keys(r.json())) & FORBIDDEN
    out = client.post("/drills/rounds/current/answer", json={"drill_id": r.json()["drill_id"], "move": "d2d4"})
    assert out.status_code == 200 and out.json()["matched"] is True
    assert client.post("/drills/rounds/current/answer", json={"drill_id": "x", "move": "d2d4"}).status_code == 409


def test_without_a_slip_file_it_is_a_plain_409(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    r = client.get("/drills/rounds/current")
    assert r.status_code == 409 and r.json()["error"] == "no_slip_drills"


def test_a_finished_round_can_still_be_read_and_an_answer_after_the_last_drill_starts_no_round(slips, conn):
    for _ in range(10):
        SR.answer(conn, SR.current(conn)["drill_id"], "d2d4")
    assert SR.current(conn)["done"] is True  # the round is finished and summarised once
    with pytest.raises(SR.RoundError) as e:
        SR.answer(conn, "anything", "d2d4")  # no round is open, and answering must not open one
    assert e.value.code == "not_current_position"
    rounds = SR.overview(conn)
    assert len(rounds) == 1 and rounds[0]["finished"] is True and rounds[0]["summary"]["matched"] == 10


def test_http_overview_lists_finished_rounds(slips):
    for _ in range(10):
        client.post("/drills/rounds/current/answer", json={"drill_id": client.get("/drills/rounds/current").json()["drill_id"], "move": "d2d4"})
    assert client.get("/drills/rounds/current").json()["done"] is True
    assert client.get("/drills/rounds").json()[0]["summary"]["matched"] == 10
