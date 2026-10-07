import json
import os
import stat

import pytest

from app.learner import baseline as b


def games(n=130):
    """Synthetic games (no personal data): alternating time controls, increasing end times."""
    return [
        {"source_id": f"https://www.chess.com/game/live/{1000 + i}", "end_time": 1_000_000 + i * 10,
         "time_control": "600" if i % 2 == 0 else "900+10"}
        for i in range(n)
    ]


def test_the_window_is_the_most_recent_games_and_ignores_other_time_controls():
    g = games() + [{"source_id": "https://www.chess.com/game/live/9999", "end_time": 9_999_999, "time_control": "180"}]
    window = b.select_window(g, 100)
    assert len(window) == 100 and window[0]["source_id"].endswith("/1129")  # newest case-study game
    assert all(w["time_control"] in b.TIME_CONTROLS for w in window)
    assert min(w["end_time"] for w in window) == 1_000_000 + 30 * 10  # games 30..129


def test_ties_on_end_time_are_broken_deterministically():
    g = [{"source_id": f"https://x/game/live/{i}", "end_time": 5, "time_control": "600"} for i in range(5)]
    first = [x["source_id"] for x in b.select_window(g, 3)]
    second = [x["source_id"] for x in b.select_window(list(reversed(g)), 3)]
    assert first == second


def test_not_enough_games_is_an_error_not_a_smaller_window():
    with pytest.raises(b.BaselineError):
        b.select_window(games(50), 100)


def test_record_keeps_the_two_time_controls_apart_with_their_own_fingerprints():
    rec = b.build_record(games())
    assert rec["n"] == 100 and set(rec["by_time_control"]) == {"10|0", "15|10"}
    assert [p["count"] for p in rec["by_time_control"].values()] == [50, 50]
    a, c = (p["sha256"] for p in rec["by_time_control"].values())
    assert a != c and rec["sha256"] not in (a, c)
    assert "no pooled" in rec["reporting"]


def test_the_fingerprint_does_not_depend_on_order_and_changes_with_any_id():
    assert b.ids_hash(["a", "b", "c"]) == b.ids_hash(["c", "a", "b"])
    assert b.ids_hash(["a", "b", "c"]) != b.ids_hash(["a", "b", "d"])


def test_freeze_writes_a_read_only_file_and_refuses_to_overwrite(tmp_path):
    path = tmp_path / "baseline" / "w.json"
    rec = b.freeze(games(), path)
    assert json.loads(path.read_text())["sha256"] == rec["sha256"]
    assert not os.stat(path).st_mode & stat.S_IWUSR  # read-only
    with pytest.raises(b.BaselineError):
        b.freeze(games(), path)


def test_verify_accepts_an_untouched_file_and_detects_a_tampered_one(tmp_path):
    path = tmp_path / "w.json"
    b.freeze(games(), path)
    assert b.verify(path)["n"] == 100
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    data = json.loads(path.read_text())
    data["by_time_control"]["10|0"]["ids"][0] = "tampered"
    path.write_text(json.dumps(data))
    with pytest.raises(b.BaselineError):
        b.verify(path)
