"""M3 missed threat in the real-game rates (ADR 0011, TASKS M3b).

Detector outcomes are scripted, so each test pins down one rule: M3 runs from M3_MIN_PLY with the position before the
opponent's move, a standing threat counts once, `also_m1` comes from M1 on the same move, a pass checks only the types still
missing, the schema v11 upgrade keeps every row, the M3 window is frozen only by `freeze`, and the Progress screen's default
stays M1 and M2.
"""

import json
import sqlite3

import chess
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.db import schema as S
from app.db.schema import connect
from app.detectors.hanging_own_v4 import Finding
from app.engine.evidence import register_config
from app.learner import pools, realgame
from app.learner import realgame_rates as RR
from tests.test_realgame_rates import CFG, FREEZE, SHORT_GAME, T_FREEZE, Scripted, add_game, result

LONG_GAME = SHORT_GAME.replace("9. h3 Nb8 *", "9. h3 Nb8 10. d4 Bg4 11. Be3 Qd7 12. Nbd2 Rfe8 13. a4 *")


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "store.sqlite3")
    register_config(c, CFG)
    yield c
    c.close()


class ScriptedM3:
    """Stand-in for `missed_threat`: `script[ply]` = (outcome, reason, origin, kind); records the `previous` positions."""

    DETECTOR = "missed_threat"
    VERSION = "1"

    def __init__(self, script, default=("no_threat", "no_concrete_threat", None, None)):
        self.script, self.default, self.calls, self.previous = script, default, [], {}

    def detect(self, board, move, ply, analyser, previous=None):
        self.calls.append(ply)
        self.previous[ply] = previous
        outcome, reason, origin, kind = self.script.get(ply, self.default)
        evidence = None if origin is None else {"threat_origin": origin, "threat_kind": kind}
        return Finding(outcome, reason, evidence)


def scripted(monkeypatch, m3, m1=None, m2=None):
    m1 = m1 or Scripted({}, "no_mistake")
    monkeypatch.setattr(RR, "DETECTORS", {"M1": m1, "M2": m2 or Scripted({}, "not_available"), "M3": m3})
    return m1


def m3_result(moves=30, counted=10, events=4, uncertain=1, details=None):
    skipped = moves - counted - uncertain  # the table refuses (and INSERT OR IGNORE drops) a row that does not add up
    assert skipped >= 0 and events <= counted
    c = {"player_moves": moves, "counted": counted, "events": events, "uncertain": uncertain, "skipped": skipped,
         "event_plies": list(range(8, 8 + 2 * events, 2))}
    c["details"] = details or {"missed_by_kind": {"capture": 3, "mate": 1}, "missed_by_origin": {"new": 4}, "also_m1": 2,
                               "met": {"defended": 5, "countered": 1}, "uncertain": {"loss_not_stable": 1},
                               "no_threat": 14, "skipped": 0, "repeats": 1}
    return {"M3": c}


# --- the per-move pass ------------------------------------------------------------------------------------------------------

def test_m3_runs_from_ply_4_and_gets_the_position_before_the_opponents_move(monkeypatch):
    m3 = ScriptedM3({})
    scripted(monkeypatch, m3)
    out = RR.analyse_game(SHORT_GAME, "white", object(), ("M3",))
    assert m3.calls[0] == 4 and all(p % 2 == 0 for p in m3.calls)  # White's plies only, from M3_MIN_PLY (ply 4 = 3.Bb5)
    prev = m3.previous[4]
    assert prev.turn == chess.BLACK and prev.fullmove_number == 2  # after 2.Nf3, before 2...Nc6
    after_nc6 = prev.copy()
    after_nc6.push_san("Nc6")
    game = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6"):
        game.push_san(san)
    assert after_nc6.board_fen() == game.board_fen()
    c = out["M3"]
    assert c["player_moves"] == len(m3.calls) and c["skipped"] == c["player_moves"] and c["details"]["no_threat"] == len(m3.calls)


def test_a_standing_threat_counts_once_until_it_is_answered(monkeypatch):
    m3 = ScriptedM3({
        8: ("missed", "all_checks_hold", "new", "capture"),
        10: ("missed", "all_checks_hold", "standing", "capture"),  # same threat, still ignored: a repeat
        12: ("met", "defended", "standing", "capture"),  # finally answered: still the same threat, a repeat
        14: ("missed", "all_checks_hold", "standing", "fork"),  # the move before was not a miss: counts
        16: ("uncertain", "loss_not_stable", "new", "mate"),
        18: ("met", "countered", "new", "fork"),
    })
    scripted(monkeypatch, m3)
    c = RR.analyse_game(LONG_GAME, "white", object(), ("M3",))["M3"]
    d = c["details"]
    assert (c["events"], c["counted"], c["uncertain"]) == (2, 3, 1)  # missed 8 and 14; met 18
    assert c["event_plies"] == [8, 14]
    assert d["repeats"] == 2 and d["met"] == {"countered": 1} and d["uncertain"] == {"loss_not_stable": 1}
    assert d["missed_by_kind"] == {"capture": 1, "fork": 1} and d["missed_by_origin"] == {"new": 1, "standing": 1}
    assert c["counted"] + c["uncertain"] + c["skipped"] == c["player_moves"]


def test_also_m1_counts_misses_that_m1_flagged_on_the_same_move(monkeypatch):
    m3 = ScriptedM3({8: ("missed", "all_checks_hold", "new", "capture"), 12: ("missed", "all_checks_hold", "new", "mate")})
    m1 = scripted(monkeypatch, m3, m1=Scripted({8: "mistake"}, "no_mistake"))
    out = RR.analyse_game(SHORT_GAME, "white", object(), ("M1", "M2", "M3"))
    assert out["M3"]["details"]["also_m1"] == 1 and out["M1"]["events"] == 1
    m1.calls.clear()
    alone = RR.analyse_game(SHORT_GAME, "white", object(), ("M3",))["M3"]
    assert alone["details"]["also_m1"] == 1 and sorted(m1.calls) == [8, 12]  # M1 only asked on the M3 misses


def test_default_types_do_not_run_m3(monkeypatch):
    m3 = ScriptedM3({})
    scripted(monkeypatch, m3)
    out = RR.analyse_game(SHORT_GAME, "white", object())
    assert set(out) == {"M1", "M2"} and m3.calls == []


def test_parse_types():
    assert RR.parse_types(None) == ("M1", "M2")
    assert RR.parse_types("m3") == ("M3",)
    assert RR.parse_types("M3, M1") == ("M1", "M3")
    with pytest.raises(ValueError):
        RR.parse_types("M4")


# --- store, resume ---------------------------------------------------------------------------------------------------------

def test_m3_row_keeps_its_details_and_m1_m2_rows_have_none(conn):
    gid = add_game(conn, 1)
    RR.store_game(conn, gid, {**result(), **m3_result()}, CFG.id)
    rows = {r["mistake_type"]: r for r in conn.execute("SELECT * FROM realgame_game WHERE game_id = ?", (gid,))}
    assert set(rows) == {"M1", "M2", "M3"}
    assert rows["M1"]["details_json"] is None and json.loads(rows["M3"]["details_json"])["also_m1"] == 2
    assert rows["M3"]["detector_version"] == "missed_threat@1+rules1"


def test_a_pass_checks_only_the_types_still_missing(conn):
    ids = [add_game(conn, f"b{i}", "600", T_FREEZE - 10_000 + i) for i in range(3)]
    realgame.freeze_baseline_window(conn, "M1", now=FREEZE)
    realgame.freeze_baseline_window(conn, "M3", now=FREEZE)
    RR.store_game(conn, ids[0], result(), CFG.id)  # M1 and M2 done for the first game
    pending, in_windows, already = RR.todo(conn, CFG.id, ("M1", "M2", "M3"))
    assert in_windows == 3 and already == 0
    assert dict(pending)[ids[0]] == ("M3",) and dict(pending)[ids[1]] == ("M1", "M3")  # M2 has no window: never asked
    RR.store_game(conn, ids[0], m3_result(), CFG.id)
    assert ids[0] not in dict(RR.todo(conn, CFG.id, ("M1", "M2", "M3"))[0])
    assert ids[0] in RR.done_games(conn, CFG.id, ("M1", "M3")) and RR.done_games(conn, CFG.id) == {ids[0]}


# --- the report --------------------------------------------------------------------------------------------------------------

def freeze_m3(conn, base_n=25, post_n=22):
    base = [add_game(conn, f"b{i}", "600", T_FREEZE - 10_000 + i) for i in range(base_n)]
    realgame.freeze_baseline_window(conn, "M3", now=FREEZE)
    post = [add_game(conn, f"a{i}", "600", T_FREEZE + i) for i in range(post_n)]
    return base, post


def test_m3_rate_is_missed_over_threats_faced_with_summed_details(conn):
    base, post = freeze_m3(conn)
    for g in base:
        RR.store_game(conn, g, m3_result(counted=10, events=4), CFG.id)
    for g in post:
        RR.store_game(conn, g, m3_result(counted=10, events=2, uncertain=1), CFG.id)
    data = RR.rates(conn, ("M3",))
    t = data["types"][0]
    assert (t["mistake_type"], t["unit"], t["label"]) == ("M3", "of threats faced", "Threats you did not answer")
    assert data["m3_min_ply"] == 4
    tc = t["time_controls"][0]
    b, a = tc["baseline"], tc["post"]
    assert (b["denominator"], b["events"], b["rate"]) == (250, 100, 0.4)
    assert a["rate"] == pytest.approx(0.2)
    assert b["details"]["also_m1"] == 50 and b["details"]["missed_by_kind"] == {"capture": 75, "mate": 25}
    assert b["details"]["met"] == {"defended": 125, "countered": 25}
    cmp = tc["comparison"]
    assert cmp["floor_unit"] == "opportunities" and cmp["state"] == "ok" and cmp["direction"] == "lower"


def test_m3_below_the_floor_is_not_enough_data(conn):
    base, post = freeze_m3(conn, 3, 2)
    for g in [*base, *post]:
        RR.store_game(conn, g, m3_result(counted=3, events=1, uncertain=1), CFG.id)
    tc = RR.rates(conn, ("M3",))["types"][0]["time_controls"][0]
    assert tc["comparison"]["state"] == "not_enough_data" and tc["comparison"]["reason"] == "below_floor"


def test_progress_screen_default_has_no_m3(conn, monkeypatch):
    freeze_m3(conn, 2, 0)
    assert [t["mistake_type"] for t in RR.rates(conn)["types"]] == ["M1", "M2"]
    assert "m3_min_ply" not in RR.rates(conn)


def test_m3_not_started_without_a_window(conn):
    t = RR.rates(conn, ("M3",))["types"][0]
    assert t["status"] == "not_started"
    assert RR.status(conn)["types"]["M3"] == "not started"


# --- freezing the M3 window --------------------------------------------------------------------------------------------------

def test_freeze_takes_the_last_30_games_once_and_never_replaces_them(conn, monkeypatch):
    monkeypatch.setattr(pools, "import_games", lambda *a, **k: 0)
    old = [add_game(conn, f"o{i}", "600", T_FREEZE - 20_000 + i) for i in range(35)]
    first = RR.freeze(conn, now=FREEZE)
    assert first["already_frozen"] is False and first["windows"][0]["games"] == 30
    assert set(realgame.frozen_windows(conn, "M3")[0]["game_ids"]) == set(old[5:])
    add_game(conn, "new", "600", T_FREEZE + 5)
    again = RR.freeze(conn)
    assert again["already_frozen"] is True and again["windows"] == first["windows"]
    with pytest.raises(sqlite3.IntegrityError, match="never edited"):
        conn.execute("UPDATE baseline_window SET game_ids_json = '[]' WHERE mistake_type = 'M3'")


def test_freeze_refuses_m1_and_m2(conn):
    with pytest.raises(ValueError):
        RR.freeze(conn, "M1")


# --- schema v11 ----------------------------------------------------------------------------------------------------------------

def store_at(path, version):
    """A store built only up to `version`, as an older copy of the code left it."""
    c = sqlite3.connect(path, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    for v in range(1, version + 1):
        step = S._MIGRATIONS[v]
        with S.transaction(c):
            if callable(step):
                step(c)
            else:
                for statement in S._split(step):
                    c.execute(statement)
            c.execute(f"PRAGMA user_version = {v}")
    return c


def test_v11_upgrade_keeps_every_row_and_the_freeze_rules(tmp_path):
    path = tmp_path / "old.sqlite3"
    c = store_at(path, 10)
    register_config(c, CFG)
    gid = add_game(c, 1)
    c.execute("INSERT INTO baseline_window (user, mistake_type, time_control, game_ids_json, frozen_at)"
              " VALUES ('me', 'M1', '600', ?, '2026-10-17T05:00:00+00:00')", (json.dumps([gid]),))
    c.execute("INSERT INTO realgame_game (game_id, mistake_type, detector_version, engine_config_id, player_moves, counted,"
              " events, uncertain, skipped, event_plies_json, rates_version, computed_at)"
              " VALUES (?, 'M1', 'hanging_own@4+rules1', ?, 30, 28, 2, 1, 1, '[8, 10]', '1', 'now')", (gid, CFG.id))
    with pytest.raises(sqlite3.IntegrityError):  # v10 refuses M3
        c.execute("INSERT INTO baseline_window (user, mistake_type, time_control, game_ids_json, frozen_at)"
                  " VALUES ('me', 'M3', '600', '[]', 'now')")
    c.close()

    up = connect(path)
    assert up.execute("PRAGMA user_version").fetchone()[0] == S.SCHEMA_VERSION == 11
    w = up.execute("SELECT * FROM baseline_window").fetchall()
    assert [(r["id"], r["mistake_type"], r["game_ids_json"]) for r in w] == [(1, "M1", json.dumps([gid]))]
    g = up.execute("SELECT * FROM realgame_game").fetchone()
    assert (g["events"], g["event_plies_json"], g["details_json"]) == (2, "[8, 10]", None)
    up.execute("INSERT INTO baseline_window (user, mistake_type, time_control, game_ids_json, frozen_at)"
               " VALUES ('me', 'M3', '600', '[]', 'now')")
    for sql, msg in [("UPDATE baseline_window SET frozen_at = 'x'", "never edited"),
                     ("DELETE FROM baseline_window", "never deleted"),
                     ("UPDATE realgame_game SET events = 0", "never edited")]:
        with pytest.raises(sqlite3.IntegrityError, match=msg):
            up.execute(sql)
    with pytest.raises(sqlite3.IntegrityError):
        up.execute("INSERT INTO baseline_window (user, mistake_type, time_control, game_ids_json, frozen_at)"
                   " VALUES ('me', 'M4', '600', '[]', 'now')")
    up.close()


def test_api_progress_still_shows_only_m1_and_m2(conn, tmp_path, monkeypatch):
    from app.api import coach

    base, _ = freeze_m3(conn, 3, 0)  # an M3 window and an M3 row exist, yet the screen's endpoint leaves them out
    RR.store_game(conn, base[0], m3_result(), CFG.id)
    monkeypatch.setattr(coach, "DB_PATH", tmp_path / "store.sqlite3")
    r = TestClient(app).get("/coach/progress/realgame")
    assert r.status_code == 200
    assert [t["mistake_type"] for t in r.json()["types"]] == ["M1", "M2"]
