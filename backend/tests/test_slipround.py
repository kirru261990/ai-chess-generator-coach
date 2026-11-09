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
FORBIDDEN = {"accepted", "evidence", "played", "played_san", "in_the_game", "matched", "checked_moves", "loss_cp", "source", "cause", "habit", "review", "why"}
SHOWN = {"done", "round", "position", "total", "drill_id", "fen", "side", "question", "legal_moves", "timer_s", "elapsed_ms"}


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
    assert hit["your_uci"] == "d2d4"  # the screen marks the answer on the board
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


def test_drills_from_an_older_finder_version_are_not_served(slips):
    old = SF.to_drill({**slip(played="oldmove"), "versions": {"slip_finder": "0", "engine_config": "ec-x"}}, "gold", 700, "own")
    with SR.slips_path().open("a") as f:
        f.write(json.dumps(old) + "\n")
    assert old["id"] not in {d["id"] for d in SR.read_slips()}


def test_a_position_used_in_an_earlier_round_is_not_offered_again_even_under_a_new_drill_id(slips, conn):
    first = [SR.current(conn)["drill_id"]]
    SR.answer(conn, first[0], "d2d4")
    for _ in range(9):
        SR.answer(conn, SR.current(conn)["drill_id"], "d2d4")
    SR.current(conn)  # finishes round 1
    used_played = {d["played"] for d in json.loads(conn.execute("SELECT drills FROM slip_round").fetchone()["drills"])}
    again = SF.to_drill({**slip(played=min(used_played)), "versions": {"slip_finder": SF.VERSION, "engine_config": "ec-new"}}, "gnew", 1, "own")
    again["avg_rating"] = 1  # the easiest drill in the pool, so it would be picked first if it were not excluded
    with SR.slips_path().open("a") as f:
        f.write(json.dumps({**again, "id": "freshid"}) + "\n")
    shown = SR.current(conn)
    assert shown["drill_id"] != "freshid"


def test_two_requests_cannot_start_two_rounds_with_the_same_drills(slips, monkeypatch):
    c_a, c_b = SR.connect(), SR.connect()
    real, state = SR.read_slips, {"ran": False}

    def interleave():
        out = real()
        if not state["ran"]:  # request B runs a whole round between A's selection and A's lock
            state["ran"] = True
            for _ in range(10):
                SR.answer(c_b, SR.current(c_b)["drill_id"], "d2d4")
            SR.current(c_b)
        return out

    monkeypatch.setattr(SR, "read_slips", interleave)
    SR.current(c_a)
    ids = [d["id"] for r in c_a.execute("SELECT drills FROM slip_round") for d in json.loads(r["drills"])]
    assert len(ids) == len(set(ids)) == 20
    c_a.close(), c_b.close()


def test_the_cause_comes_with_the_answer_never_before_it_and_an_unlabelled_drill_reads_as_other(slips, conn):
    from app.learner import slipcause

    shown = SR.current(conn)
    assert "cause" not in json.dumps(shown)  # the leak rule: nothing about why before the answer
    why = {"mine": {"step": 1, "text": "t", "arrows": [], "squares": []}, "better": None}
    slipcause.save({shown["drill_id"]: {"cause": "hanging_own", "detector": "hanging_own", "version": slipcause.DETECTORS[0][1], "why": why, "why_version": slipcause.slipwhy.VERSION}})
    got = SR.answer(conn, shown["drill_id"], "a2a3")
    assert got["cause"]["cause"] == "hanging_own" and "piece" in got["cause"]["sentence"] and got["cause"]["habit"]
    assert got["cause"]["why"] == why
    nxt = SR.current(conn)
    other = SR.answer(conn, nxt["drill_id"], "d2d4")["cause"]
    assert other["cause"] == "other" and other["habit"] is None


def backdate(conn, seconds):
    """Pretend the position was shown `seconds` ago (the server's clock decides over time, not the browser's)."""
    from datetime import UTC, datetime, timedelta

    conn.execute("UPDATE slip_attempt SET shown_at = ? WHERE answered_at IS NULL",
                 ((datetime.now(UTC) - timedelta(seconds=seconds)).isoformat(timespec="milliseconds"),))
    conn.commit()


def test_the_timer_defaults_to_15_seconds_accepts_8_or_none_and_refuses_anything_else(slips, conn):
    assert SR.current(conn)["timer_s"] == 15
    for bad in (7, -1, 600):
        with pytest.raises(SR.RoundError) as e:
            SR.current(conn, timer_s=bad)
        assert e.value.code == "bad_timer"
    assert SR.current(conn, timer_s=8)["timer_s"] == 15  # the setting is fixed when the position is first shown
    assert SR.answer(conn, SR.current(conn)["drill_id"], "d2d4")["timer_s"] == 15


def test_an_answer_after_the_limit_is_saved_and_marked_over_time_by_the_servers_clock(slips, conn):
    shown = SR.current(conn, timer_s=8)
    backdate(conn, 20)
    late = SR.answer(conn, shown["drill_id"], "d2d4")
    assert late["over_time"] is True and late["matched"] is True and late["timer_s"] == 8 and late["elapsed_ms"] >= 20000
    quick = SR.current(conn, timer_s=8)
    assert SR.answer(conn, quick["drill_id"], "d2d4")["over_time"] is False


def test_with_no_timer_nothing_is_over_time_and_the_round_summary_counts_over_time_answers(slips, conn):
    shown = SR.current(conn, timer_s=0)
    backdate(conn, 300)
    assert SR.answer(conn, shown["drill_id"], "d2d4")["over_time"] is False
    for n in range(9):
        s = SR.current(conn, timer_s=15)
        if n < 3:
            backdate(conn, 30)
        SR.answer(conn, s["drill_id"], "d2d4")
    done = SR.current(conn)
    assert done["summary"]["over_time"] == 3 and done["summary"]["timer_s"] == {"0": 1, "15": 9}


def test_http_timer_query_and_a_bad_timer_is_a_400(slips):
    assert client.get("/drills/rounds/current?timer=8").json()["timer_s"] == 8
    r = client.get("/drills/rounds/current?timer=9")
    assert r.status_code == 400 and r.json()["error"] == "bad_timer"


def test_an_older_ledger_without_the_timer_columns_is_upgraded_in_place(slips):
    import sqlite3

    SR.ledger_path().unlink(missing_ok=True)
    old = sqlite3.connect(SR.ledger_path())
    old.executescript("""CREATE TABLE slip_round (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, round_version TEXT NOT NULL,
        drills TEXT NOT NULL, finished_at TEXT);
        CREATE TABLE slip_attempt (round_id INTEGER NOT NULL, drill_id TEXT NOT NULL, position INTEGER NOT NULL, shown_at TEXT NOT NULL,
        answered_at TEXT, move_uci TEXT, matched INTEGER, elapsed_ms INTEGER, assisted INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (round_id, drill_id));""")
    old.close()
    c = SR.connect()
    assert SR.current(c)["timer_s"] == 15
    c.close()


def test_the_round_version_records_that_the_round_had_a_timer(slips, conn):
    for _ in range(10):
        SR.answer(conn, SR.current(conn)["drill_id"], "d2d4")
    assert SR.current(conn)["summary"]["versions"]["round"] == "2"  # v1 rounds had no timer


def test_an_unreadable_label_file_never_costs_the_player_an_answer(slips, conn):
    from app.learner import slipcause

    shown = SR.current(conn)
    slipcause.causes_path().write_text("")  # what a reader sees while a rewrite is in progress
    got = SR.answer(conn, shown["drill_id"], "d2d4")
    assert got["matched"] is True and got["cause"]["cause"] == "other"
    slipcause.causes_path().write_text("{not json")
    assert slipcause.load() == {}


def test_saving_labels_replaces_the_file_whole_and_leaves_no_temporary_file(slips):
    from app.learner import slipcause

    slipcause.save({"a": {"cause": "other", "detector": None, "version": slipcause.SET_VERSION}})
    slipcause.save({"b": {"cause": "other", "detector": None, "version": slipcause.SET_VERSION}})
    assert set(slipcause.load()) == {"b"} and [p.name for p in slipcause.causes_path().parent.glob("slip_causes*")] == ["slip_causes_v1.json"]


def test_two_first_requests_on_an_old_ledger_both_upgrade_it_without_a_duplicate_column_error(slips):
    import sqlite3
    import threading

    SR.ledger_path().unlink(missing_ok=True)
    old = sqlite3.connect(SR.ledger_path())
    old.executescript("""CREATE TABLE slip_round (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, round_version TEXT NOT NULL,
        drills TEXT NOT NULL, finished_at TEXT);
        CREATE TABLE slip_attempt (round_id INTEGER NOT NULL, drill_id TEXT NOT NULL, position INTEGER NOT NULL, shown_at TEXT NOT NULL,
        answered_at TEXT, move_uci TEXT, matched INTEGER, elapsed_ms INTEGER, assisted INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (round_id, drill_id));""")
    old.close()
    errors, gate = [], threading.Barrier(8)

    def go():
        try:
            gate.wait()
            SR.connect().close()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == []


def test_an_unfinished_version_1_round_stays_untimed_until_it_is_finished(slips, conn):
    SR.current(conn)
    conn.execute("UPDATE slip_round SET round_version = '1'")
    conn.execute("DELETE FROM slip_attempt")
    conn.commit()
    shown = SR.current(conn, timer_s=15)
    assert shown["timer_s"] == 0  # version 1 means untimed (ADR 0021)
    backdate(conn, 60)
    assert SR.answer(conn, shown["drill_id"], "d2d4")["over_time"] is False
    for _ in range(9):
        SR.answer(conn, SR.current(conn, timer_s=15)["drill_id"], "d2d4")
    assert SR.current(conn, timer_s=15)["done"] is True  # the version 1 round is finished
    assert SR.current(conn, timer_s=15)["timer_s"] == 15  # the next round is version 2 and timed


def test_the_review_lines_come_with_the_answer_only_and_an_answer_without_stored_lines_still_works(slips, conn):
    from app.learner import slipline

    shown = SR.current(conn)
    assert "review" not in json.dumps(shown)
    d = next(x for x in slips if x["id"] == shown["drill_id"])
    slipline.save({d["id"]: {"mine": ["a2a3", "e7e5"], "better": ["d2d4", "d7d5"], "engine_config": d["versions"]["engine_config"], "plies": slipline.PLIES}})
    got = SR.answer(conn, shown["drill_id"], "d2d4")
    assert got["review"]["start_fen"] == START
    assert [s["san"] for s in got["review"]["mine"]] == ["a3", "e5"] and [s["who"] for s in got["review"]["better"]] == ["you", "they"]
    other = SR.answer(conn, SR.current(conn)["drill_id"], "d2d4")
    assert other["review"] is None and other["matched"] is True  # no lines stored for this one: the answer is not lost


def test_a_position_shown_again_reports_how_long_the_server_has_been_counting(slips, conn):
    first = SR.current(conn, timer_s=15)
    assert first["elapsed_ms"] < 2000
    backdate(conn, 9)
    again = SR.current(conn, timer_s=15)  # a reload or Continue: the clock did not restart
    assert again["drill_id"] == first["drill_id"] and 9000 <= again["elapsed_ms"] < 12000


def test_drills_listed_in_the_exclusion_file_are_not_served_and_an_unreadable_file_excludes_nothing(slips):
    ids = [d["id"] for d in slips[:2]]
    (SR.slips_path().parent / "slip_excluded_v1.json").write_text(json.dumps({i: {"reason": "slip_not_confirmed_at_depth_24"} for i in ids}))
    served = {d["id"] for d in SR.read_slips()}
    assert not served & set(ids) and len(served) == len(slips) - 2
    (SR.slips_path().parent / "slip_excluded_v1.json").write_text("{not json")
    assert len(SR.read_slips()) == len(slips)


def test_an_exclusion_file_that_is_not_a_map_of_drill_ids_excludes_nothing_and_a_caller_can_ask_for_every_drill(slips):
    path = SR.slips_path().parent / "slip_excluded_v1.json"
    path.write_text(json.dumps("abc"))
    assert len(SR.read_slips()) == len(slips)  # not the letters a, b, c
    path.write_text(json.dumps({slips[0]["id"]: {"reason": "x"}}))
    assert len(SR.read_slips()) == len(slips) - 1
    assert len(SR.read_slips(include_excluded=True)) == len(slips)
