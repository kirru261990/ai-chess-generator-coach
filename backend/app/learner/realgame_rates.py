"""Real-game rates with floors (PRD v2 §8, Step 4b; ADR 0006 decision 43).

Did the owner's actual play change? Per mistake type and per time control, the frozen baseline window (`realgame.py`) is
compared with the post window (every game played at or after the freeze, same time control). The two never share a game.

- **M1 rate:** hanging-piece mistakes per 100 player moves, from MIN_PLY on. A move counts when `hanging_own` v4 said
  `mistake` or `no_mistake`.
- **M2 rate:** missed free captures ÷ free captures available. An opportunity is a move where `missed_free` v3 said `missed`
  or `taken`; a position with no free capture is not an opportunity.
- **Abstain, do not guess (AGENTS rule 5):** `uncertain` moves are in neither the numerator nor the denominator, and are
  shown as a count. Decided positions and positions with one legal move are skipped by the detectors and are not counted.
- **Same detectors, same engine config:** every game is checked move by move at the evidence config (depth 18, MultiPV 3;
  `engine/evidence.py`), the same config the practice positions use. Rows made by another detector version or config are never
  summed with these (a different config is a different row, PRD §4.1).
- **Floors:** a before/after comparison needs at least FLOOR_GAMES games (M1) or FLOOR_OPPORTUNITIES opportunities (M2) in
  each window. Otherwise the answer is "Not enough data yet" and the two windows are still shown with their denominators.
- **Not started:** a type with no frozen window shows "not started". This module never freezes a window.

The numbers are directional evidence, not proof of cause: a window is a few dozen games, the player's opponents and
openings differ from window to window, and practice is not the only thing that changed.

Resumable: one row per game, type, detector and config in `realgame_game` (schema v10); a pass skips games already done.

  uv run python -m app.learner.realgame_rates status              # windows, how many games are analysed
  uv run python -m app.learner.realgame_rates run [--workers 4]   # import new games, check every player move (resumable)
  uv run python -m app.learner.realgame_rates report              # the rates, as the Progress screen shows them
"""

from __future__ import annotations

import argparse
import io
import json
import math
import multiprocessing as mp
import sqlite3
import sys
import time
from datetime import UTC, datetime

import chess
import chess.pgn

from app import config
from app.db.schema import connect, default_path, transaction
from app.detectors import hanging_own_v4, missed_free_v3
from app.detectors import prd_rules as R
from app.learner import pools, realgame
from app.learner.assessment import LABELS, TYPES, user
from app.learner.evidence_run import games_path

RATES_VERSION = "1"
FLOOR_GAMES = 20
FLOOR_OPPORTUNITIES = 20
DETECTORS = {"M1": hanging_own_v4, "M2": missed_free_v3}
LABEL = "directional evidence, not proof of cause"
TIME_CONTROL_LABELS = {"600": "10 min", "900+10": "15 min + 10 s"}


def detector_tag(mtype: str) -> str:
    m = DETECTORS[mtype]
    return f"{m.DETECTOR}@{m.VERSION}+rules{R.RULES_VERSION}"


def current_tags() -> dict[str, str]:
    return {t: detector_tag(t) for t in TYPES}


# --- the per-move pass over one game ----------------------------------------------------------------------------------

def analyse_game(pgn: str, user_color: str, analyser) -> dict[str, dict]:
    """Run both detectors over every player move from MIN_PLY on. Returns {type: counts} for `realgame_game`.

    `analyser` is an `EvidenceAnalyser` (or a scripted stand-in with `analyse(board, depth=None)` and `.config`).
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or game.errors:
        raise ValueError("the PGN could not be read")
    white = user_color == "white"
    out = {t: {"player_moves": 0, "counted": 0, "events": 0, "uncertain": 0, "skipped": 0, "event_plies": []} for t in TYPES}
    board = game.board()
    for ply, node in enumerate(game.mainline()):
        move = node.move
        if (ply % 2 == 0) == white and ply >= R.MIN_PLY:
            for t in TYPES:
                finding = DETECTORS[t].detect(board, move, ply, analyser)
                c = out[t]
                c["player_moves"] += 1
                if finding.outcome == "uncertain":
                    c["uncertain"] += 1
                elif finding.outcome in ("mistake", "missed"):
                    c["counted"] += 1
                    c["events"] += 1
                    c["event_plies"].append(ply)
                elif finding.outcome in ("no_mistake", "taken"):
                    c["counted"] += 1
                else:  # skipped (decided, only legal move) or not_available (no free capture): not an opportunity
                    c["skipped"] += 1
        board.push(move)
    return out


def store_game(conn: sqlite3.Connection, game_id: str, result: dict[str, dict], config_id: str) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with transaction(conn):
        for t, c in result.items():
            conn.execute(
                "INSERT OR IGNORE INTO realgame_game (game_id, mistake_type, detector_version, engine_config_id, player_moves,"
                " counted, events, uncertain, skipped, event_plies_json, rates_version, computed_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (game_id, t, detector_tag(t), config_id, c["player_moves"], c["counted"], c["events"], c["uncertain"],
                 c["skipped"], json.dumps(c["event_plies"]), RATES_VERSION, now),
            )


# --- windows -----------------------------------------------------------------------------------------------------------

def freeze_time(conn: sqlite3.Connection, mtype: str) -> int | None:
    row = conn.execute(
        "SELECT MIN(frozen_at) FROM baseline_window WHERE user = ? AND mistake_type = ?", (user(), mtype)).fetchone()
    return None if row[0] is None else int(datetime.fromisoformat(row[0]).timestamp())


def post_game_ids(conn: sqlite3.Connection, mtype: str, time_control: str) -> list[str]:
    """Games played at or after the freeze (the baseline took those strictly before it), never a baseline game."""
    frozen = freeze_time(conn, mtype)
    if frozen is None:
        return []
    baseline = {g for w in realgame.frozen_windows(conn, mtype) if w["time_control"] == time_control for g in w["game_ids"]}
    return [r[0] for r in conn.execute(
        "SELECT id FROM game WHERE time_control = ? AND played_at >= ? AND user_color IS NOT NULL ORDER BY played_at, id",
        (time_control, frozen)) if r[0] not in baseline]


def games_to_analyse(conn: sqlite3.Connection) -> list[str]:
    """Every game in a frozen window or after a freeze, for any type (a game is checked once for both detectors)."""
    ids: dict[str, None] = {}
    for t in TYPES:
        for w in realgame.frozen_windows(conn, t):
            ids.update(dict.fromkeys(w["game_ids"]))
            ids.update(dict.fromkeys(post_game_ids(conn, t, w["time_control"])))
    return list(ids)


def done_games(conn: sqlite3.Connection, config_id: str) -> set[str]:
    """Games with a current-version row for every type under this engine config."""
    tags = current_tags()
    rows = conn.execute(
        "SELECT game_id, mistake_type, detector_version FROM realgame_game WHERE engine_config_id = ?", (config_id,))
    have: dict[str, set[str]] = {}
    for r in rows:
        if tags.get(r["mistake_type"]) == r["detector_version"]:
            have.setdefault(r["game_id"], set()).add(r["mistake_type"])
    return {g for g, ts in have.items() if ts == set(TYPES)}


# --- the rates ---------------------------------------------------------------------------------------------------------

def _wilson(events: int, n: int) -> tuple[float, float] | None:
    """95% Wilson range for events / n, as a share. It shows how wide the doubt is with so few events."""
    if n <= 0:
        return None
    z, p = 1.96, events / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def _window(rows: list[sqlite3.Row], ids: list[str], mtype: str) -> dict:
    mine = [r for r in rows if r["game_id"] in set(ids)]
    games = len(mine)
    counted = sum(r["counted"] for r in mine)
    events = sum(r["events"] for r in mine)
    interval = _wilson(events, counted)
    scale = 100 if mtype == "M1" else 1
    return {
        "games_in_window": len(ids), "games": games, "missing_games": len(ids) - games,
        "player_moves": sum(r["player_moves"] for r in mine),
        "denominator": counted, "events": events, "uncertain": sum(r["uncertain"] for r in mine),
        "skipped": sum(r["skipped"] for r in mine),
        "rate": events / counted * scale if counted else None,
        "interval": None if interval is None else [interval[0] * scale, interval[1] * scale],
    }


def _comparison(mtype: str, before: dict, after: dict) -> dict:
    floor_unit = "games" if mtype == "M1" else "opportunities"
    have = (lambda w: w["games"]) if mtype == "M1" else (lambda w: w["denominator"])
    floor = FLOOR_GAMES if mtype == "M1" else FLOOR_OPPORTUNITIES
    out = {"floor": floor, "floor_unit": floor_unit, "baseline_has": have(before), "post_has": have(after)}
    incomplete = before["missing_games"] or after["missing_games"]
    if incomplete:
        return {**out, "state": "analysis_incomplete"}
    if have(before) < floor or have(after) < floor:
        return {**out, "state": "not_enough_data"}
    ib, ia = before["interval"], after["interval"]
    change = after["rate"] - before["rate"]
    overlap = not (ia[0] > ib[1] or ib[0] > ia[1])
    return {**out, "state": "ok", "change": change,
            "direction": "lower" if change < 0 else "higher" if change > 0 else "same",
            "ranges_overlap": overlap}


def _choose_config(rows: list[sqlite3.Row]) -> str | None:
    if not rows:
        return None
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["engine_config_id"]] = counts.get(r["engine_config_id"], 0) + 1
    return max(counts, key=lambda c: (counts[c], max(r["computed_at"] for r in rows if r["engine_config_id"] == c)))


def rates(conn: sqlite3.Connection) -> dict:
    """The Progress screen's real-game section: per type, per time control, both windows with their denominators."""
    tags = current_tags()
    out_types, configs = [], set()
    for t in TYPES:
        windows = realgame.frozen_windows(conn, t)
        entry: dict = {"mistake_type": t, "label": LABELS[t], "detector": tags[t], "unit": "per 100 player moves" if t == "M1"
                       else "of free captures available"}
        if not windows:
            out_types.append({**entry, "status": "not_started", "frozen_at": None, "time_controls": []})
            continue
        rows = conn.execute(
            "SELECT * FROM realgame_game WHERE mistake_type = ? AND detector_version = ?", (t, tags[t])).fetchall()
        config_id = _choose_config(rows)
        rows = [r for r in rows if r["engine_config_id"] == config_id]
        if config_id:
            configs.add(config_id)
        tcs = []
        for w in windows:
            tc = w["time_control"]
            before = _window(rows, w["game_ids"], t)
            after = _window(rows, post_game_ids(conn, t, tc), t)
            tcs.append({"time_control": tc, "label": TIME_CONTROL_LABELS.get(tc, tc), "baseline": before, "post": after,
                        "comparison": _comparison(t, before, after)})
        out_types.append({**entry, "status": "started", "frozen_at": windows[0]["frozen_at"], "engine_config_id": config_id,
                          "time_controls": tcs})
    return {"rates_version": RATES_VERSION, "label": LABEL, "floors": {"games": FLOOR_GAMES, "opportunities": FLOOR_OPPORTUNITIES},
            "engine_config_ids": sorted(configs), "min_ply": R.MIN_PLY, "types": out_types}


# --- worker side: one pinned engine per process (as in evidence_run) --------------------------------------------------------

_worker: dict = {}


def _init_worker(db_path: str) -> None:
    from app.engine.evidence import open_evidence

    conn = connect(db_path)
    ctx = open_evidence(conn)
    _worker["analyser"] = ctx.__enter__()
    _worker["ctx"] = ctx


def _process(task: dict) -> dict:
    analyser = _worker["analyser"]
    started = time.monotonic()
    try:
        result = analyse_game(task["pgn"], task["user_color"], analyser)
        error = None
    except ValueError as e:  # one unreadable game must not stop the pass; it stays missing and the rates say so
        result, error = None, f"{type(e).__name__}: {e}"
    return {"game": task["game"], "result": result, "error": error, "config_id": analyser.config.id,
            "seconds": time.monotonic() - started}


def run(workers: int, limit: int | None = None) -> dict:
    db_path = default_path()
    conn = connect(db_path)
    added = pools.import_games(conn, games_path(), config.case_study_time_controls())
    from app.engine.evidence import open_evidence

    with open_evidence(conn) as probe:  # the config id of this engine, to know what is already done
        config_id = probe.config.id
    all_ids = games_to_analyse(conn)
    finished = done_games(conn, config_id)
    todo_ids = [g for g in all_ids if g not in finished]
    already = len(all_ids) - len(todo_ids)
    if limit:
        todo_ids = todo_ids[:limit]
    tasks = []
    for gid in todo_ids:
        r = conn.execute("SELECT pgn, user_color FROM game WHERE id = ?", (gid,)).fetchone()
        tasks.append({"game": gid, "pgn": r["pgn"], "user_color": r["user_color"]})
    print(f"{added} games imported; {len(all_ids)} games in the windows, {already} already done, {len(tasks)} to check "
          f"at {config_id}; {workers} engine processes", flush=True)
    started, done, failed = time.monotonic(), 0, []
    if tasks:
        ctx = mp.get_context("spawn")
        with ctx.Pool(workers, initializer=_init_worker, initargs=(str(db_path),)) as pool:
            for i, res in enumerate(pool.imap_unordered(_process, tasks), 1):
                if res["error"]:
                    failed.append((res["game"], res["error"]))
                else:
                    store_game(conn, res["game"], res["result"], res["config_id"])
                    done += 1
                if i % 5 == 0 or i == len(tasks):
                    mins = (time.monotonic() - started) / 60
                    eta = mins / i * (len(tasks) - i)
                    print(f"  {i}/{len(tasks)} games, {mins:.1f} min, about {eta:.0f} min left", flush=True)
    for gid, err in failed:
        print(f"  could not check a game ({gid.split(':')[0]}): {err}", flush=True)
    return {"imported": added, "checked": done, "failed": len(failed), "engine_config_id": config_id}


def status(conn: sqlite3.Connection) -> dict:
    out = {"rates_version": RATES_VERSION, "detectors": current_tags(), "types": {}}
    for t in TYPES:
        ws = realgame.frozen_windows(conn, t)
        out["types"][t] = [{"time_control": w["time_control"], "frozen_at": w["frozen_at"],
                            "baseline_games": len(w["game_ids"]),
                            "post_games": len(post_game_ids(conn, t, w["time_control"]))} for w in ws] or "not started"
    rows = conn.execute("SELECT engine_config_id, COUNT(DISTINCT game_id) AS n FROM realgame_game GROUP BY 1").fetchall()
    out["games_checked_by_config"] = {r["engine_config_id"]: r["n"] for r in rows}
    out["games_to_check"] = len(games_to_analyse(conn))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.learner.realgame_rates")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--limit", type=int, default=None, help="only the first N games still to check (to try it out)")
    sub.add_parser("status")
    sub.add_parser("report")
    args = p.parse_args(argv)
    if args.cmd == "run":
        print(json.dumps(run(args.workers, args.limit), indent=1))
    elif args.cmd == "status":
        print(json.dumps(status(connect()), indent=1))
    else:
        print(json.dumps(rates(connect()), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
