"""PRD v2 Step 4b: real-game rates with floors (PRD §8, ADR 0006 decision 43).

Detector outcomes are scripted, so each test pins down one rule: what counts in the numerator and the denominator, that
abstentions are in neither, the floors, that the two windows never share a game, and that the frozen baseline is only read.
"""

import json
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api import coach
from app.api.main import app
from app.db.schema import connect
from app.detectors.hanging_own_v4 import Finding
from app.engine.evidence import EngineConfig, register_config
from app.learner import realgame
from app.learner import realgame_rates as RR
from app.mcp import practice_tools as T

CFG = EngineConfig("Stockfish 19", "nn-test.nnue", "sha", depth=18, multipv=3, hash_mb=64, threads=1)
FREEZE = datetime(2026, 10, 17, 5, 0, tzinfo=UTC)
T_FREEZE = int(FREEZE.timestamp())
SHORT_GAME = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 *"


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "store.sqlite3")
    register_config(c, CFG)
    yield c
    c.close()


class Scripted:
    """Stand-in for a detector module: `outcomes[ply]` picks the finding; every call is recorded."""

    DETECTOR = "x"
    VERSION = "0"

    def __init__(self, outcomes, default):
        self.outcomes, self.default, self.calls = outcomes, default, []

    def detect(self, board, move, ply, analyser):
        self.calls.append(ply)
        return Finding(self.outcomes.get(ply, self.default), "scripted")


def add_game(conn, n, tc="600", played_at=0, color="white", pgn=SHORT_GAME):
    gid = f"chesscom:r{n}"
    conn.execute(
        "INSERT INTO game (id, source, platform_id, user_color, time_control, played_at, pool, pgn)"
        " VALUES (?, 'chesscom', ?, ?, ?, ?, 'PRACTICE', ?)", (gid, f"r{n}", color, tc, played_at, pgn))
    return gid


def result(moves=30, counted=28, events=2, uncertain=1, skipped=1):
    assert counted + uncertain + skipped == moves
    return {t: {"player_moves": moves, "counted": counted, "events": events, "uncertain": uncertain, "skipped": skipped,
                "event_plies": list(range(8, 8 + 2 * events, 2))} for t in ("M1", "M2")}


def freeze_m1(conn, tc="600", before=30):
    """Freeze M1 with `before` games before T_FREEZE; returns the baseline game ids."""
    ids = [add_game(conn, f"b{i}", tc, T_FREEZE - 10_000 + i) for i in range(before)]
    realgame.freeze_baseline_window(conn, "M1", now=FREEZE)
    return ids


# --- the per-move pass ------------------------------------------------------------------------------------------------------

def test_analyse_game_counts_only_the_players_moves_from_min_ply(monkeypatch):
    m1 = Scripted({8: "mistake", 10: "uncertain", 12: "skipped"}, "no_mistake")
    m2 = Scripted({8: "missed", 12: "taken"}, "not_available")
    monkeypatch.setattr(RR, "DETECTORS", {"M1": m1, "M2": m2})
    pgn = SHORT_GAME.replace("9. h3 Nb8 *", "9. h3 Nb8 10. d4 Bg4 11. Be3 Qd7 12. Nbd2 Rfe8 13. a4 *")
    out = RR.analyse_game(pgn, "white", object())
    assert m1.calls == [8, 10, 12, 14, 16, 18, 20, 22, 24][: len(m1.calls)] and min(m1.calls) == 8  # never before MIN_PLY
    assert all(p % 2 == 0 for p in m1.calls)  # White's plies only
    a, b = out["M1"], out["M2"]
    for c in (a, b):
        assert c["counted"] + c["uncertain"] + c["skipped"] == c["player_moves"]
    assert (a["events"], a["uncertain"], a["skipped"]) == (1, 1, 1) and a["event_plies"] == [8]
    assert a["counted"] == a["player_moves"] - 2
    assert b["events"] == 1 and b["counted"] == 2 and b["skipped"] == b["player_moves"] - 2  # no free capture is no opportunity
    assert b["uncertain"] == 0


def test_analyse_game_as_black_uses_black_plies(monkeypatch):
    m1 = Scripted({}, "no_mistake")
    monkeypatch.setattr(RR, "DETECTORS", {"M1": m1, "M2": Scripted({}, "not_available")})
    RR.analyse_game(SHORT_GAME, "black", object())
    assert m1.calls and all(p % 2 == 1 and p >= 8 for p in m1.calls)


def test_an_unreadable_pgn_is_refused(monkeypatch):
    monkeypatch.setattr(RR, "DETECTORS", {"M1": Scripted({}, "no_mistake"), "M2": Scripted({}, "no_mistake")})
    with pytest.raises(ValueError):
        RR.analyse_game("1. e4 e5 2. Ke5 *", "white", object())


def test_a_game_result_is_stored_once_and_never_edited(conn):
    gid = add_game(conn, 1)
    RR.store_game(conn, gid, result(), CFG.id)
    RR.store_game(conn, gid, result(events=0), CFG.id)  # a repeat is ignored, not a second row
    rows = conn.execute("SELECT * FROM realgame_game WHERE game_id = ?", (gid,)).fetchall()
    assert len(rows) == 2 and {r["mistake_type"] for r in rows} == {"M1", "M2"} and all(r["events"] == 2 for r in rows)
    assert {r["rates_version"] for r in rows} == {RR.RATES_VERSION}
    assert rows[0]["detector_version"] == RR.detector_tag(rows[0]["mistake_type"])
    with pytest.raises(Exception, match="never edited"):
        conn.execute("UPDATE realgame_game SET events = 0")


# --- the windows ------------------------------------------------------------------------------------------------------------

def test_post_window_is_everything_from_the_freeze_on_and_never_a_baseline_game(conn):
    base = freeze_m1(conn, "600", 30)
    ten_after = [add_game(conn, f"a{i}", "600", T_FREEZE + i) for i in range(5)]  # the first is played in the freeze second
    other_tc = add_game(conn, "x", "900+10", T_FREEZE + 50)
    add_game(conn, "late", "600", T_FREEZE - 1)  # one second before the freeze: not post, not in the window of 30 either
    post = RR.post_game_ids(conn, "M1", "600")
    assert sorted(post) == sorted(ten_after)
    assert not set(post) & set(base)
    assert other_tc not in post
    assert RR.post_game_ids(conn, "M2", "600") == []  # M2 is not frozen: it has no post window


def test_games_to_analyse_covers_both_windows_only(conn):
    base = freeze_m1(conn, "600", 3)
    after = [add_game(conn, f"a{i}", "600", T_FREEZE + i) for i in range(2)]
    add_game(conn, "old", "600", T_FREEZE - 99_999)  # before the window of 3 games
    assert set(RR.games_to_analyse(conn)) == set(base) | set(after)


def test_done_games_needs_every_type_at_this_config_and_the_current_detector(conn):
    gid = add_game(conn, 1)
    RR.store_game(conn, gid, result(), CFG.id)
    assert RR.done_games(conn, CFG.id) == {gid}
    assert RR.done_games(conn, "ec-other") == set()
    other = add_game(conn, 2)
    RR.store_game(conn, other, {"M1": result()["M1"]}, CFG.id)  # only one type stored
    assert RR.done_games(conn, CFG.id) == {gid}


# --- the rates and their floors ---------------------------------------------------------------------------------------------

def fill_windows(conn, base_n=30, post_n=25, base=None, post=None):
    base_ids = freeze_m1(conn, "600", base_n)
    post_ids = [add_game(conn, f"a{i}", "600", T_FREEZE + i) for i in range(post_n)]
    for g in base_ids:
        RR.store_game(conn, g, base or result(), CFG.id)
    for g in post_ids:
        RR.store_game(conn, g, post or result(), CFG.id)
    return base_ids, post_ids


def m1_tc(conn):
    data = RR.rates(conn)
    t = next(x for x in data["types"] if x["mistake_type"] == "M1")
    return data, t, t["time_controls"][0]


def test_m1_rate_is_events_per_100_counted_moves_with_every_denominator(conn):
    fill_windows(conn, 30, 25, base=result(30, 28, 3, 1, 1), post=result(30, 28, 1, 1, 1))
    data, t, tc = m1_tc(conn)
    assert data["rates_version"] == RR.RATES_VERSION and data["engine_config_ids"] == [CFG.id]
    assert t["status"] == "started" and t["detector"] == RR.detector_tag("M1")
    b, p = tc["baseline"], tc["post"]
    assert (b["games"], b["player_moves"], b["denominator"], b["events"]) == (30, 900, 840, 90)
    assert (b["uncertain"], b["skipped"]) == (30, 30)  # abstentions are shown, and left out of the rate
    assert b["rate"] == pytest.approx(90 / 840 * 100)
    assert (p["games"], p["denominator"], p["events"]) == (25, 700, 25) and p["rate"] == pytest.approx(25 / 700 * 100)
    c = tc["comparison"]
    assert c["state"] == "ok" and c["direction"] == "lower" and c["change"] == pytest.approx(p["rate"] - b["rate"])
    assert b["interval"][0] < b["rate"] < b["interval"][1]
    assert data["label"] == "directional evidence, not proof of cause"


def test_m1_floor_is_twenty_games_in_each_window(conn):
    fill_windows(conn, 30, 19)
    assert m1_tc(conn)[2]["comparison"]["state"] == "not_enough_data"
    assert m1_tc(conn)[2]["comparison"]["baseline_has"] == 30 and m1_tc(conn)[2]["comparison"]["post_has"] == 19


def test_m1_floor_met_at_exactly_twenty(conn):
    fill_windows(conn, 30, 20)
    assert m1_tc(conn)[2]["comparison"]["state"] == "ok"


def test_a_baseline_window_with_fewer_than_twenty_games_gives_no_comparison(conn):
    fill_windows(conn, 12, 30)
    c = m1_tc(conn)[2]["comparison"]
    assert c["state"] == "not_enough_data" and c["baseline_has"] == 12


def test_unchecked_games_are_never_guessed_at(conn):
    fill_windows(conn, 30, 25)
    extra = add_game(conn, "new", "600", T_FREEZE + 999)  # played after the freeze, not checked yet
    c = m1_tc(conn)[2]
    assert c["post"]["missing_games"] == 1 and c["post"]["games_in_window"] == 26
    assert c["comparison"]["state"] == "analysis_incomplete"
    RR.store_game(conn, extra, result(), CFG.id)
    assert m1_tc(conn)[2]["comparison"]["state"] == "ok"


def test_m2_is_not_started_without_a_frozen_window_and_is_never_frozen_here(conn):
    fill_windows(conn)
    data = RR.rates(conn)
    m2 = next(x for x in data["types"] if x["mistake_type"] == "M2")
    assert m2["status"] == "not_started" and m2["time_controls"] == []
    assert realgame.frozen_windows(conn, "M2") == []
    RR.rates(conn)
    RR.status(conn)
    assert realgame.frozen_windows(conn, "M2") == []


def freeze_both(conn, n_base=30, n_post=25):
    base = [add_game(conn, f"b{i}", "600", T_FREEZE - 10_000 + i) for i in range(n_base)]
    realgame.freeze_baseline_window(conn, "M1", now=FREEZE)
    realgame.freeze_baseline_window(conn, "M2", now=FREEZE)
    post = [add_game(conn, f"a{i}", "600", T_FREEZE + i) for i in range(n_post)]
    return base, post


def test_m2_rate_is_missed_over_opportunities_and_the_floor_counts_opportunities(conn):
    base, post = freeze_both(conn, 30, 25)
    for g in base:  # 1 opportunity per game, 30 in the window
        RR.store_game(conn, g, {**result(), "M2": {"player_moves": 30, "counted": 1, "events": 1, "uncertain": 2, "skipped": 27,
                                                   "event_plies": [8]}}, CFG.id)
    for g in post[:19]:  # 19 opportunities after: under the floor even with 25 games
        RR.store_game(conn, g, {**result(), "M2": {"player_moves": 30, "counted": 1, "events": 0, "uncertain": 0, "skipped": 29,
                                                   "event_plies": []}}, CFG.id)
    for g in post[19:]:
        RR.store_game(conn, g, {**result(), "M2": {"player_moves": 30, "counted": 0, "events": 0, "uncertain": 0, "skipped": 30,
                                                   "event_plies": []}}, CFG.id)
    t = next(x for x in RR.rates(conn)["types"] if x["mistake_type"] == "M2")
    tc = t["time_controls"][0]
    assert t["status"] == "started" and tc["baseline"]["denominator"] == 30 and tc["baseline"]["events"] == 30
    assert tc["baseline"]["rate"] == 1.0 and tc["baseline"]["uncertain"] == 60  # uncertain moves are in neither number
    assert tc["post"]["denominator"] == 19 and tc["post"]["games"] == 25
    c = tc["comparison"]
    assert c["state"] == "not_enough_data" and c["floor_unit"] == "opportunities" and c["post_has"] == 19
    RR.store_game(conn, add_game(conn, "one-more", "600", T_FREEZE + 500), {**result(), "M2": {
        "player_moves": 30, "counted": 1, "events": 0, "uncertain": 0, "skipped": 29, "event_plies": []}}, CFG.id)
    t = next(x for x in RR.rates(conn)["types"] if x["mistake_type"] == "M2")
    assert t["time_controls"][0]["post"]["denominator"] == 20 and t["time_controls"][0]["comparison"]["state"] == "ok"
    assert t["time_controls"][0]["comparison"]["change"] == pytest.approx(-1.0)


def test_rows_from_another_detector_version_or_engine_config_are_never_summed(conn):
    _, post_ids = fill_windows(conn, 30, 25)
    register_config(conn, CFG.at_depth(12))
    stale = add_game(conn, "stale", "600", T_FREEZE + 700)
    RR.store_game(conn, stale, result(events=9, uncertain=0, skipped=0, moves=30, counted=30), CFG.at_depth(12).id)
    conn.execute(
        "INSERT INTO realgame_game SELECT game_id, mistake_type, 'old@1+rules0', engine_config_id, player_moves, counted, events,"
        " uncertain, skipped, event_plies_json, rates_version, computed_at FROM realgame_game WHERE game_id = ?", (post_ids[0],))
    _, t, tc = m1_tc(conn)
    assert tc["post"]["games"] == 25 and tc["post"]["events"] == 50  # 25 games x 2; the depth-12 and old-version rows are ignored
    assert tc["post"]["missing_games"] == 1  # the depth-12 game is not checked at this config
    assert t["engine_config_id"] == CFG.id


def test_windows_created_together_are_reported_per_time_control(conn):
    for i in range(30):
        add_game(conn, f"t{i}", "600", T_FREEZE - 9_000 + i)
        add_game(conn, f"f{i}", "900+10", T_FREEZE - 9_000 + i)
    realgame.freeze_baseline_window(conn, "M1", now=FREEZE)
    post = [add_game(conn, "p600", "600", T_FREEZE + 1), add_game(conn, "p900", "900+10", T_FREEZE + 2)]
    for g in [r[0] for r in conn.execute("SELECT id FROM game")]:
        RR.store_game(conn, g, result(), CFG.id)
    t = next(x for x in RR.rates(conn)["types"] if x["mistake_type"] == "M1")
    labels = {x["time_control"]: x["label"] for x in t["time_controls"]}
    assert labels == {"600": "10 min", "900+10": "15 min + 10 s"}
    for x in t["time_controls"]:
        assert x["post"]["games"] == 1 and x["baseline"]["games"] == 30  # each time control keeps its own games
        assert x["comparison"]["state"] == "not_enough_data"
    assert post


def test_overlapping_ranges_are_flagged_and_a_clear_gap_is_not(conn):
    fill_windows(conn, 30, 30, base=result(30, 30, 1, 0, 0), post=result(30, 30, 1, 0, 0))
    assert m1_tc(conn)[2]["comparison"]["ranges_overlap"] is True
    c2 = connect(":memory:")
    register_config(c2, CFG)
    fill_windows(c2, 30, 30, base=result(30, 30, 10, 0, 0), post=result(30, 30, 0, 0, 0))
    c = m1_tc(c2)[2]["comparison"]
    assert c["ranges_overlap"] is False and c["direction"] == "lower"


def test_reading_the_rates_never_writes_the_baseline(conn):
    fill_windows(conn)
    dump = lambda: conn.execute("SELECT * FROM baseline_window ORDER BY id").fetchall()
    before = [tuple(r) for r in dump()]
    RR.rates(conn)
    RR.status(conn)
    RR.games_to_analyse(conn)
    assert [tuple(r) for r in dump()] == before
    assert json.loads(before[0][4])  # still the same frozen list


# --- surfaces ---------------------------------------------------------------------------------------------------------------

def test_the_mcp_text_shows_denominators_and_the_floor_message(conn):
    fill_windows(conn, 30, 5)
    text = "\n".join(T.realgame_lines(RR.rates(conn)))
    assert "directional evidence, not proof of cause" in text
    assert "Not enough data yet" in text and "of 840 player moves" in text
    assert "not started" in text  # M2


def test_the_endpoint_returns_the_rates(conn, tmp_path, monkeypatch):
    fill_windows(conn, 30, 25)
    monkeypatch.setattr(coach, "DB_PATH", tmp_path / "store.sqlite3")

    @contextmanager
    def no_engine(_conn):
        raise AssertionError("the endpoint must not start an engine")
        yield

    monkeypatch.setattr(coach, "open_analyser", no_engine)
    r = TestClient(app).get("/coach/progress/realgame")
    assert r.status_code == 200
    body = r.json()
    assert body["rates_version"] == RR.RATES_VERSION and body["floors"] == {"games": 20, "opportunities": 20}
    assert {t["mistake_type"]: t["status"] for t in body["types"]} == {"M1": "started", "M2": "not_started"}


def test_freeze_time_is_the_earliest_freeze(conn):
    assert RR.freeze_time(conn, "M1") is None
    freeze_m1(conn, "600", 2)
    assert RR.freeze_time(conn, "M1") == T_FREEZE
