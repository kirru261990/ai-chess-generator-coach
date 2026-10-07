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


def other_games(offset, n=130):
    """A different synthetic set of games: same shape, distinct game ids."""
    return [{**g, "source_id": f"https://www.chess.com/game/live/{offset + i}"} for i, g in enumerate(games(n))]


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


def manifest_for(rec, tmp_path, name="manifest.json"):
    """An independent record of a window: fingerprints and counts only, as the committed manifest has."""
    path = tmp_path / name
    path.write_text(json.dumps({
        "version": 1, "rule": rec["rule"], "n": rec["n"], "sha256": rec["sha256"],
        "by_time_control": {k: {"count": v["count"], "sha256": v["sha256"]} for k, v in rec["by_time_control"].items()},
    }))
    return path


def test_verify_accepts_an_untouched_file_and_detects_a_tampered_one(tmp_path):
    path = tmp_path / "w.json"
    manifest = manifest_for(b.freeze(games(), path), tmp_path)
    assert b.verify(path, manifest)["n"] == 100
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    data = json.loads(path.read_text())
    data["by_time_control"]["10|0"]["ids"][0] = "tampered"
    path.write_text(json.dumps(data))
    with pytest.raises(b.BaselineError):
        b.verify(path, manifest)


def test_a_replacement_window_cannot_vouch_for_itself(tmp_path):
    # Review finding: verify() used to compare the file with hashes taken from the same file, so a
    # different 100-game window passed. It must be checked against the independently recorded manifest.
    real = b.freeze(other_games(1000), tmp_path / "real.json")
    manifest = manifest_for(real, tmp_path)
    fake = tmp_path / "fake.json"
    b.freeze(other_games(5000), fake)  # a different window, internally consistent
    with pytest.raises(b.BaselineError, match="independently recorded"):
        b.verify(fake, manifest)


def test_swapped_time_control_lists_are_detected(tmp_path):
    path = tmp_path / "w.json"
    manifest = manifest_for(b.freeze(games(), path), tmp_path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    data = json.loads(path.read_text())
    tc = data["by_time_control"]
    tc["10|0"], tc["15|10"] = tc["15|10"], tc["10|0"]  # reversed cohorts; the file's own hashes still agree
    path.write_text(json.dumps(data))
    with pytest.raises(b.BaselineError):
        b.verify(path, manifest)


def test_verify_fails_closed_without_the_independent_record(tmp_path):
    path = tmp_path / "w.json"
    b.freeze(games(), path)
    with pytest.raises(b.BaselineError, match="no independent record"):
        b.verify(path, tmp_path / "missing.json")


def test_freeze_refuses_a_window_that_differs_from_the_recorded_one(tmp_path):
    manifest = manifest_for(b.build_record(other_games(1000)), tmp_path)
    with pytest.raises(b.BaselineError, match="independently recorded"):
        b.freeze(other_games(5000), tmp_path / "w.json", manifest_path=manifest)
    assert not (tmp_path / "w.json").exists()
    b.freeze(other_games(1000), tmp_path / "ok.json", manifest_path=manifest)  # the recorded window itself is accepted


def test_two_concurrent_freezes_cannot_both_succeed(tmp_path):
    # Review finding: the existence check and the write were separate steps, so two interleaved calls both
    # reported success and only one survived. Creation is now exclusive.
    import pathlib
    import threading

    target = tmp_path / "w.json"
    barrier = threading.Barrier(2)
    real_exists = pathlib.Path.exists

    def exists_then_wait(self):  # both threads pass the existence check before either writes
        found = real_exists(self)
        if self == target:
            try:
                barrier.wait(timeout=2)
            except threading.BrokenBarrierError:
                pass
        return found

    results = []

    def run(offset):
        try:
            results.append(("ok", b.freeze(other_games(offset), target)["sha256"]))
        except b.BaselineError:
            results.append(("refused", None))

    pathlib.Path.exists = exists_then_wait
    try:
        threads = [threading.Thread(target=run, args=(o,)) for o in (1000, 5000)]
        [t.start() for t in threads]
        [t.join() for t in threads]
    finally:
        pathlib.Path.exists = real_exists
    assert sorted(r[0] for r in results) == ["ok", "refused"]
    winner = next(r[1] for r in results if r[0] == "ok")
    assert json.loads(target.read_text())["sha256"] == winner  # the file on disk is the winner's, intact


def test_the_committed_manifest_matches_the_adr_and_the_owners_frozen_file():
    from pathlib import Path

    manifest = json.loads(b.MANIFEST_PATH.read_text())
    adr = (b.MANIFEST_PATH.parent / "0002-baseline-window.md").read_text()
    for value in (manifest["sha256"], *(v["sha256"] for v in manifest["by_time_control"].values())):
        assert value in adr  # the ADR table and the manifest cannot drift apart
    assert "ids" not in manifest and all("ids" not in v for v in manifest["by_time_control"].values())  # no game ids in the repo
    frozen = Path(b.baseline_path())
    if frozen.exists():  # only on the owner's machine (the games are never committed)
        assert b.verify(frozen)["sha256"] == manifest["sha256"]
