"""Pools are fixed per game at import (PRD v2 §5.1, ADR 0006)."""

import json

from app.db.schema import connect
from app.learner import pools


def test_pool_is_a_function_of_the_game_alone():
    assert pools.pool_for("123456789") == pools.pool_for("123456789")
    share = sum(pools.pool_for(str(i)) == "HELDOUT" for i in range(4000)) / 4000
    assert 0.37 < share < 0.43


def write_games(path, games):
    path.write_text("".join(json.dumps(g) + "\n" for g in games))


def game(i, tc="600"):
    return {"source_id": f"https://www.chess.com/game/live/{i}", "user_color": "white", "time_control": tc,
            "end_time": 1_000 + i, "pgn": "1. e4 *"}


def test_import_assigns_pools_once_and_skips_other_time_controls(tmp_path):
    conn = connect(":memory:")
    path = tmp_path / "games.jsonl"
    write_games(path, [game(i) for i in range(30)] + [game(99, tc="180")])
    assert pools.import_games(conn, path, {"600"}) == 30
    before = {r["id"]: r["pool"] for r in conn.execute("SELECT id, pool FROM game")}
    assert all(before[pools.row_id(str(i))] == pools.pool_for(str(i)) for i in range(30))
    write_games(path, [game(i) for i in range(40)])  # new games arrive
    assert pools.import_games(conn, path, {"600"}) == 10
    after = {r["id"]: r["pool"] for r in conn.execute("SELECT id, pool FROM game")}
    assert all(after[k] == v for k, v in before.items())  # earlier games keep their pool
    counts = pools.pool_counts(conn)["600"]
    assert counts["HELDOUT"] + counts["PRACTICE"] == 40
