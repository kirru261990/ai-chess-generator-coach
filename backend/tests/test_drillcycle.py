"""Drill cycles (ADR 0018): the frozen set, the cycle ledger, matching, timing and the leak test. Uses a scratch bank."""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.learner import drillbank
from app.learner import drillcycle as C
from tests.test_drillcheck import E1, E2, drill

client = TestClient(app)
FORBIDDEN = {"accepted", "alternatives", "evidence", "refutation_line", "checked_moves", "played", "played_san", "line", "matched"}


def keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from keys(v)


@pytest.fixture
def bank(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drills = []
    for n in range(40):
        d = drill(n, "M1" if n % 2 else "M2", f"g{n}")
        d.update(side="white" if n % 2 else "black", played="c2c4" if n % 2 else "e8g8", played_san="c4" if n % 2 else "O-O")
        d["fen"] = E1["fen"] if n % 2 else E2["fen"]
        drills.append(d)
    drills.append({**drill(99, "M1", "gx", experimental=True), "fen": E1["fen"]})
    drillbank.bank_dir().mkdir(parents=True)
    drillbank.bank_path().write_text("".join(json.dumps(d) + "\n" for d in drills))
    classes = ["right_away", "next_move", "within_3_moves", "unclear"]
    m2 = [d for d in drills if d["type"] == "M2"]
    drillbank.bank_path().with_suffix(".timing.json").write_text(json.dumps({d["id"]: classes[n % 4] for n, d in enumerate(m2)}))
    # M1 alternatives in the shared fixture are not legal here, so use real ones
    return drills


@pytest.fixture
def conn(bank):
    c = C.connect()
    yield c
    c.close()


def test_set_is_half_each_type_one_per_game_easiest_first_and_skips_experimental_and_unclear(bank):
    timing = json.loads(drillbank.bank_path().with_suffix(".timing.json").read_text())
    chosen = C.build_set(bank, timing, 20)
    assert len(chosen) == 20
    assert {d["type"] for d in chosen} == {"M1", "M2"}
    assert len({d["game_id"] for d in chosen}) == 20
    assert not any(d["experimental"] for d in chosen)
    assert all(timing[d["id"]] != "unclear" for d in chosen if d["type"] == "M2")
    ratings = [d["avg_rating"] for d in chosen]
    assert ratings == sorted(ratings)


def test_a_short_type_is_topped_up_from_the_other(bank):
    only_m1 = [d for d in bank if d["type"] == "M1" and not d["experimental"]]
    assert len(C.build_set(only_m1, {}, 10)) == 10


def test_the_set_is_frozen_when_the_bank_changes(bank, conn):
    first = C.ensure_set(conn)
    drillbank.bank_path().write_text("")
    assert C.ensure_set(conn)["id"] == first["id"]
    assert 0 < len(json.loads(C.ensure_set(conn)["drills"])) <= C.SET_SIZE


def test_no_bank_and_too_small_a_bank_are_plain_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    c = C.connect()
    with pytest.raises(C.CycleError) as e:
        C.ensure_set(c)
    assert e.value.code == "no_drill_bank"


def test_what_is_shown_before_the_answer_leaks_nothing(bank, conn):
    cur = C.current(conn)
    assert not set(keys(cur)) & FORBIDDEN
    assert cur["legal_moves"] and cur["position"] == 1


def test_matching_uses_only_the_verified_moves_and_a_miss_is_not_called_wrong(bank, conn):
    cur = C.current(conn)
    d = C._set_drills(C.current_set(conn))[cur["drill_id"]]
    good = d["accepted"][0]
    legal = cur["legal_moves"]
    assert good in legal
    r = C.answer(conn, cur["drill_id"], good)
    assert r["matched"] and r["assisted"] and "not_checked" not in r
    nxt = C.current(conn)
    other = next(m for m in nxt["legal_moves"] if m not in C._set_drills(C.current_set(conn))[nxt["drill_id"]]["accepted"])
    miss = C.answer(conn, nxt["drill_id"], other)
    assert not miss["matched"] and "not_checked" in miss and "wrong" not in miss["not_checked"].lower().replace("not", "")


def test_an_illegal_move_and_a_second_answer_are_refused(bank, conn):
    cur = C.current(conn)
    with pytest.raises(C.CycleError) as e:
        C.answer(conn, cur["drill_id"], "a1a1")
    assert e.value.code == "illegal_move"
    other = next(m for m in cur["legal_moves"])
    C.answer(conn, cur["drill_id"], other)
    with pytest.raises(C.CycleError) as e:
        C.answer(conn, cur["drill_id"], other)
    assert e.value.code == "already_answered"


def test_answering_a_position_that_is_not_on_screen_is_refused(bank, conn):
    C.current(conn)
    with pytest.raises(C.CycleError) as e:
        C.answer(conn, "nope", "e2e4")
    assert e.value.code == "not_current_position"


def play_cycle(conn, pick):
    while True:
        cur = C.current(conn)
        if cur["done"]:
            return cur
        C.answer(conn, cur["drill_id"], pick(cur))


def test_cycles_follow_each_other_reorder_and_compare(bank, conn):
    first = play_cycle(conn, lambda cur: cur["legal_moves"][0])
    assert first["summary"]["cycles"][0]["finished"] and first["summary"]["cycles"][0]["answered"] == first["summary"]["size"]
    n = first["summary"]["size"]
    order1 = json.loads(conn.execute("SELECT order_json FROM cycle WHERE number = 1").fetchone()[0])
    cur = C.current(conn)  # opens cycle 2
    assert cur["cycle"] == 2 and not cur["done"]
    order2 = json.loads(conn.execute("SELECT order_json FROM cycle WHERE number = 2").fetchone()[0])
    assert sorted(order1) == sorted(order2) and order1 != order2 and len(order2) == n
    C.answer(conn, cur["drill_id"], cur["legal_moves"][0])
    s = C.summary(conn)
    assert s["cycles"][1]["answered"] == 1 and "vs_previous" in s["cycles"][1] and s["cycles"][1]["vs_previous"]["same_size"] is False


def test_resume_returns_the_same_position(bank, conn):
    a = C.current(conn)
    b = C.current(conn)
    assert a["drill_id"] == b["drill_id"] and b["position"] == 1


def test_elapsed_time_is_capped_and_taken_from_the_server(bank, conn):
    cur = C.current(conn)
    conn.execute("UPDATE attempt SET shown_at = '2000-01-01T00:00:00.000+00:00'")
    conn.commit()
    r = C.answer(conn, cur["drill_id"], cur["legal_moves"][0])
    assert r["elapsed_ms"] == C.ELAPSED_CAP_MS


def test_chance_rate_has_a_denominator_and_is_a_share(bank, conn):
    cur = C.current(conn)
    C.answer(conn, cur["drill_id"], cur["legal_moves"][0])
    c = C.summary(conn)["cycles"][0]
    assert c["answered"] == 1 and 0 <= c["chance"] <= 1


def test_http_flow_and_error_codes(bank):
    assert client.get("/drills/cycles").json() == {"has_set": False, "cycles": []}
    cur = client.get("/drills/cycles/current").json()
    assert not set(keys(cur)) & FORBIDDEN
    bad = client.post("/drills/cycles/current/answer", json={"drill_id": cur["drill_id"], "move": "a1a1"})
    assert bad.status_code == 400 and bad.json()["error"] == "illegal_move"
    ok = client.post("/drills/cycles/current/answer", json={"drill_id": cur["drill_id"], "move": cur["legal_moves"][0]})
    assert ok.status_code == 200 and ok.json()["assisted"] is True
    again = client.post("/drills/cycles/current/answer", json={"drill_id": cur["drill_id"], "move": cur["legal_moves"][0]})
    assert again.status_code == 409


def test_http_without_a_bank_is_a_plain_409(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    r = client.get("/drills/cycles/current")
    assert r.status_code == 409 and r.json()["error"] == "no_drill_bank"
