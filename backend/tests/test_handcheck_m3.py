"""M3 hand-check (TASKS M3d): the games stay out of the M3 window, the sample is fixed and balanced, the score rule is strict."""

import json
from datetime import UTC, datetime

import chess
import pytest

from app.db.schema import connect
from app.detectors.hanging_own_v4 import Finding
from app.learner import handcheck_m3 as H
from app.learner import realgame
from app.learner import realgame_rates as RR

PGN = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 *"
SCHOLAR = chess.Board()
for san in ("e4", "e5", "Qh5", "Nc6", "Bc4"):
    SCHOLAR.push_san(san)
EVIDENCE = {"mistake_type": "M3", "fen": SCHOLAR.fen(), "ply": 5, "threat_move": {"uci": "h5f7", "san": "Qxf7#"},
            "threat_line": {"uci": ["h5f7"], "san": ["Qxf7#"]}, "threat_kind": "mate", "threat_origin": "new",
            "best_move": {"uci": "g7g6", "san": "g6"}, "player_move": {"uci": "g8f6", "san": "Nf6"}, "eval_loss": 1500,
            "threat_size_cp": 900}


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "store.sqlite3")
    yield c
    c.close()


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(H.config, "DATA_DIR", tmp_path)
    return tmp_path


def add_games(conn, n, tc="600", start=1):
    ids = []
    for i in range(start, start + n):
        gid = f"chesscom:g{tc}-{i}"
        conn.execute("INSERT INTO game (id, source, platform_id, user_color, time_control, played_at, pool, pgn)"
                     " VALUES (?, 'chesscom', ?, 'white', ?, ?, 'PRACTICE', ?)", (gid, gid, tc, i, PGN))
        ids.append(gid)
    return ids


def test_older_games_are_all_but_the_latest_window_and_nothing_is_older_with_a_short_history(conn):
    ids = add_games(conn, 40)
    add_games(conn, 12, tc="900+10")
    older = H.older_games(conn)
    assert set(older["600"]) == set(ids[:10])  # played_at 1..10; the latest 30 are 11..40
    assert older["900+10"] == []  # fewer games than a window: nothing is older


def test_once_the_m3_window_is_frozen_older_means_before_it_and_never_a_later_game(conn):
    ids = add_games(conn, 40)
    realgame.freeze_baseline_window(conn, "M3", now=datetime(1970, 1, 1, 0, 10, tzinfo=UTC))  # after all 40 games
    add_games(conn, 5, start=100)  # games after the freeze
    older = H.older_games(conn)["600"]
    window = set(realgame.frozen_windows(conn, "M3")[0]["game_ids"])
    assert not set(older) & window and set(older) == set(ids[:10])
    assert all(not g.endswith(("-100", "-101", "-102", "-103", "-104")) for g in older)


def test_a_game_the_owner_judged_in_an_earlier_version_is_never_used_again(conn, data_dir):
    ids = add_games(conn, 40)
    (data_dir / "evidence").mkdir()
    (data_dir / "evidence" / "handcheck_m3_v1.json").write_text(json.dumps({"items": [{"game": ids[0]}, {"game": ids[1]}]}))
    assert set(H.older_games(conn)["600"]) == set(ids[2:10])


def test_older_games_come_newest_first(conn):
    ids = add_games(conn, 40)
    assert H.older_games(conn)["600"] == list(reversed(ids[:10]))


def test_scan_order_is_fixed(conn):
    add_games(conn, 50)
    assert H.older_games(conn) == H.older_games(conn)


class Scripted:
    DETECTOR, VERSION = "x", "0"

    def __init__(self, outcomes, evidence):
        self.outcomes, self.evidence, self.calls = outcomes, evidence, []

    def detect(self, board, move, ply, analyser, previous=None):
        self.calls.append(ply)
        return Finding(self.outcomes.get(ply, "met"), "scripted", self.evidence)


def test_analyse_game_collects_missed_moves_but_not_a_repeat_of_the_same_threat(monkeypatch):
    standing = {**EVIDENCE, "threat_origin": "standing"}
    m3 = Scripted({8: "missed", 10: "missed", 12: "missed"}, standing)
    m1 = Scripted({8: "mistake"}, {})
    monkeypatch.setattr(RR, "DETECTORS", {"M1": m1, "M2": m1, "M3": m3})
    found = []
    RR.analyse_game(PGN, "white", object(), ("M3",), collect=found)
    assert [f["ply"] for f in found] == [8]  # 10 and 12 repeat the same standing threat
    assert found[0]["move"] and found[0]["evidence"]["threat_move"]["uci"] == "h5f7" and found[0]["also_m1"] is True


def flagged(n_games, tc, *, with_flags=True, start=0):
    out = {}
    for i in range(start, start + n_games):
        gid = f"chesscom:{tc}-{i}"
        flags = [{"ply": 8, "fen": SCHOLAR.fen(), "move": "g8f6", "evidence": EVIDENCE, "also_m1": False},
                 {"ply": 12, "fen": SCHOLAR.fen(), "move": "g8f6", "evidence": EVIDENCE, "also_m1": False}] if with_flags else []
        out[gid] = {"game": gid, "time_control": tc, "played_at": 1000 - i, "flags": flags, "error": None}
    return out


def test_sample_is_fifteen_per_time_control_one_per_game_and_fixed():
    scanned = {**flagged(20, "600"), **flagged(18, "900+10"), **flagged(10, "900+10", with_flags=False, start=100)}
    picked = H.sample(scanned)
    assert len(picked) == 30 and len({p["game"] for p in picked}) == 30
    assert sum(p["time_control"] == "600" for p in picked) == 15 and sum(p["time_control"] == "900+10" for p in picked) == 15
    assert [p["id"] for p in picked] == [f"m3c-{i:02d}" for i in range(1, 31)]
    assert H.sample(scanned) == picked


def test_the_sample_is_the_newest_flagged_games_shown_newest_to_oldest():
    scanned = {**flagged(20, "600"), **flagged(18, "900+10")}  # played_at 1000 - i: a smaller i is newer
    picked = H.sample(scanned)
    assert [p["played_at"] for p in picked] == sorted((p["played_at"] for p in picked), reverse=True)
    assert {p["game"] for p in picked if p["time_control"] == "600"} == {f"chesscom:600-{i}" for i in range(15)}


def test_sample_refuses_to_run_short():
    with pytest.raises(SystemExit):
        H.sample({**flagged(20, "600"), **flagged(14, "900+10")})


def test_make_freezes_the_sample_and_the_page_asks_three_questions(data_dir):
    H.evidence_dir().mkdir(parents=True)
    rows = {**flagged(16, "600"), **flagged(16, "900+10")}
    H.scan_path().write_text("".join(json.dumps(r) + "\n" for r in rows.values()))
    page = H.make().read_text()
    first = H.key_path().read_text()
    for gid in list(rows)[:5]:  # a later scan cannot change the frozen sample
        H.scan_path().write_text(H.scan_path().read_text() + json.dumps({**rows[gid], "game": gid + "x"}) + "\n")
    H.make()
    assert H.key_path().read_text() == first
    assert page.count('<section class="card" id="m3c-') == 30
    for q in ("A.", "B.", "C."):
        assert q in page
    assert "Qxf7" not in page and "eval" not in page.lower()  # notation and engine numbers stay off the page; plain words only


def key_for(tmp):
    items = [{"id": f"m3c-{i:02d}", "time_control": "600" if i <= 15 else "900+10",
              "flag": {"ply": 8, "fen": SCHOLAR.fen(), "move": "g8f6", "evidence": EVIDENCE, "also_m1": False}}
             for i in range(1, 31)]
    H.evidence_dir().mkdir(parents=True, exist_ok=True)
    H.key_path().write_text(json.dumps({"items": items}))


def all_yes(ids):
    return "\n".join(f"{i}: A yes, B yes, C yes" for i in ids)


def test_score_needs_yes_to_every_question_and_the_gate_is_27(data_dir):
    key_for(data_dir)
    ids = [f"m3c-{i:02d}" for i in range(1, 31)]
    lines = all_yes(ids).splitlines()
    lines[0] = "m3c-01: A yes, B no, C -"
    lines[1] = "m3c-02: A cant, B -, C -"
    lines[2] = "m3c-03: A yes, B yes, C cant"
    r = H.score("\n".join(lines))
    assert (r["real"], r["of"], r["passed"], r["unanswered"]) == (27, 30, True, [])
    assert r["by_time_control"] == {"600": {"real": 12, "of": 15}, "900+10": {"real": 15, "of": 15}}
    lines[3] = "m3c-04: A no, B -, C -"
    assert H.score("\n".join(lines))["passed"] is False


def test_an_unanswered_question_is_reported_and_is_not_real(data_dir):
    key_for(data_dir)
    r = H.score("m3c-01: A yes, B yes, C -\nm3c-02: A no, B -, C -")
    assert "m3c-01" in r["unanswered"] and "m3c-02" not in r["unanswered"] and r["real"] == 0
    assert len(r["unanswered"]) == 29  # the others have no answers at all


def test_the_page_script_is_valid_javascript(tmp_path):
    import re
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = re.search(r"<script>(.*)</script>", H.PAGE, re.DOTALL).group(1)
    file = tmp_path / "page.js"
    file.write_text(script.replace("__KEY__", "k").replace("__TOTAL__", "30"))
    done = subprocess.run([node, "--check", str(file)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr


class FakeCtx:
    """Stand-in for the spawn context: a pool that runs the (patched) worker in this process."""

    def Pool(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def imap_unordered(self, fn, tasks):
        return iter([fn(t) for t in tasks])


def test_scan_ends_when_a_game_cannot_be_read_and_never_submits_it_twice(conn, tmp_path, data_dir, monkeypatch):
    add_games(conn, 31)  # one game older than the latest 30
    bad = "chesscom:g600-1"
    conn.execute("UPDATE game SET pgn = 'not a pgn' WHERE id = ?", (bad,))
    conn.close()
    calls = []

    def process(task):
        calls.append(task["game"])
        assert len(calls) == 1, "the unreadable game was submitted again"  # fail fast instead of looping forever
        return {"game": task["game"], "time_control": task["time_control"], "flags": [], "config_id": "c",
                "error": "ValueError: the PGN could not be read", "seconds": 0.0}

    monkeypatch.setattr(H, "_process", process)
    monkeypatch.setattr(H.mp, "get_context", lambda name: FakeCtx())
    monkeypatch.setattr(H.pools, "import_games", lambda *a, **k: 0)
    summary = H.scan(tmp_path / "store.sqlite3", 1)
    assert calls == [bad]  # asked once, then the scan reports the shortfall and stops
    assert summary["with_flag"] == {} and summary["older_games"]["600"] == 1
    assert H.read_scan()[bad]["error"]
