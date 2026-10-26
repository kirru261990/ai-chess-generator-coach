"""Real-game rates with floors (PRD v2 §8, Step 4b; ADR 0006 decision 43).

Did the owner's actual play change? Per mistake type and per time control, the frozen baseline window (`realgame.py`) is
compared with the post window (every game played at or after the freeze, same time control). The two never share a game.

- **M1 rate:** hanging-piece mistakes per 100 player moves, from MIN_PLY on. A move counts when `hanging_own` v4 said
  `mistake` or `no_mistake`.
- **M2 rate:** missed free captures ÷ free captures available. An opportunity is a move where `missed_free` v3 said `missed`
  or `taken`; a position with no free capture is not an opportunity.
- **M3 rate** (ADR 0011): missed threats ÷ threats faced (missed + met), from M3_MIN_PLY on. A repeat of a standing threat
  (the threat was already there and the player's previous move missed it) counts once: the repeat is skipped and logged in
  `details_json`. M3 is only run and reported when asked (`--types M3`); the Progress screen shows M1 and M2.
- **Abstain, do not guess (AGENTS rule 5):** `uncertain` moves are in neither the numerator nor the denominator, and are
  shown as a count. Decided positions and positions with one legal move are skipped by the detectors and are not counted.
- **Same detectors, same engine config:** every game is checked move by move at the evidence config (depth 18, MultiPV 3;
  `engine/evidence.py`), the same config the practice positions use. Rows made by another detector version or config are never
  summed with these (a different config is a different row, PRD §4.1).
- **Floors:** a before/after comparison needs at least FLOOR_GAMES games (M1) or FLOOR_OPPORTUNITIES opportunities (M2) in
  each window. Otherwise the answer is "Not enough data yet" and the two windows are still shown with their denominators.
- **Not started:** a type with no frozen window shows "not started". M1 and M2 windows are frozen by their first practice
  session; the M3 window only by the `freeze` command (M3 has no practice yet), never by `run` or `report`.

The numbers are directional evidence, not proof of cause: a window is a few dozen games, the player's opponents and
openings differ from window to window, and practice is not the only thing that changed.

Resumable: one row per game, type, detector and config in `realgame_game` (schema v11); a pass skips what is already done,
per type.

  uv run python -m app.learner.realgame_rates status                       # windows, how many games are analysed
  uv run python -m app.learner.realgame_rates run [--workers 4]            # import new games, check M1 and M2 (resumable)
  uv run python -m app.learner.realgame_rates report                       # the M1 and M2 rates, as the Progress screen shows them
  uv run python -m app.learner.realgame_rates freeze                       # freeze the M3 window once (last 30 games per time control)
  uv run python -m app.learner.realgame_rates run --types M3 [--workers 4]  # check M3 in the M3 windows
  uv run python -m app.learner.realgame_rates report --types M3            # the M3 rate, kinds, overlap with M1
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
from app.detectors import hanging_own_v4, missed_free_v3, missed_threat
from app.detectors import prd_rules as R
from app.learner import pools, realgame
from app.learner.assessment import LABELS, TYPES, user
from app.learner.evidence_run import games_path

RATES_VERSION = "1"
FLOOR_GAMES = 20
FLOOR_OPPORTUNITIES = 20
RATE_TYPES = (*TYPES, "M3")  # M3 (ADR 0011) is run and reported only when asked; TYPES stays the default
DETECTORS = {"M1": hanging_own_v4, "M2": missed_free_v3, "M3": missed_threat}
TYPE_LABELS = {**LABELS, "M3": "Threats you did not answer"}
UNITS = {"M1": "per 100 player moves", "M2": "of free captures available", "M3": "of threats faced"}
LABEL = "directional evidence, not proof of cause"
TIME_CONTROL_LABELS = {"600": "10 min", "900+10": "15 min + 10 s"}


def detector_tag(mtype: str) -> str:
    m = DETECTORS[mtype]
    return f"{m.DETECTOR}@{m.VERSION}+rules{R.RULES_VERSION}"


def current_tags(types=RATE_TYPES) -> dict[str, str]:
    return {t: detector_tag(t) for t in types}


def first_ply(mtype: str) -> int:
    return R.M3_MIN_PLY if mtype == "M3" else R.MIN_PLY


def parse_types(text: str | None) -> tuple[str, ...]:
    """`"M1,M3"` -> ("M1", "M3") in RATE_TYPES order; None -> TYPES (M1 and M2, as before M3)."""
    if not text:
        return TYPES
    asked = {t.strip().upper() for t in text.split(",") if t.strip()}
    unknown = asked - set(RATE_TYPES)
    if unknown or not asked:
        raise ValueError(f"types must be among {', '.join(RATE_TYPES)}")
    return tuple(t for t in RATE_TYPES if t in asked)


# --- the per-move pass over one game ----------------------------------------------------------------------------------

def _empty(mtype: str) -> dict:
    c = {"player_moves": 0, "counted": 0, "events": 0, "uncertain": 0, "skipped": 0, "event_plies": []}
    if mtype == "M3":
        c["details"] = {"missed_by_kind": {}, "missed_by_origin": {}, "also_m1": 0, "met": {}, "uncertain": {},
                        "no_threat": 0, "skipped": 0, "repeats": 0}
    return c


def _count(c: dict, finding, ply: int) -> None:
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


def _bump(d: dict, key: str) -> None:
    d[key] = d.get(key, 0) + 1


def _threat_id(finding) -> str | None:
    """The threat's identity across two player turns: its threat move (UCI), or None when the record has none."""
    move = (finding.evidence or {}).get("threat_move") or {}
    return move.get("uci")


def _count_m3(c: dict, finding, ply: int, last: tuple[str, str | None] | None, m1_finding) -> tuple[str, str | None]:
    """Count one M3 finding. Returns (outcome, threat id) for the next player move's repeat rule.

    A repeat (ADR 0011 decision 5) is the **same** ignored threat: this threat is `standing`, the previous player move
    `missed` a threat, and both have the same threat move. `standing` alone is not enough (PR 97 review): with two threats on
    the board, the pass search may pick threat A on one turn and threat B on the next, and B is a new opportunity. A standing
    threat's line already worked before the opponent's last move, so the same threat keeps the same first move. With no
    threat move on record, nothing is called a repeat.
    """
    c["player_moves"] += 1
    d, ev = c["details"], finding.evidence or {}
    tid = _threat_id(finding)
    if (finding.outcome in ("missed", "met") and ev.get("threat_origin") == "standing" and last is not None
            and last[0] == "missed" and tid is not None and tid == last[1]):
        c["skipped"] += 1
        d["repeats"] += 1
        return finding.outcome, tid
    if finding.outcome == "missed":
        c["counted"] += 1
        c["events"] += 1
        c["event_plies"].append(ply)
        _bump(d["missed_by_kind"], ev.get("threat_kind", "other"))
        _bump(d["missed_by_origin"], ev.get("threat_origin", "unknown"))
        if m1_finding is not None and m1_finding.outcome == "mistake":
            d["also_m1"] += 1
    elif finding.outcome == "met":
        c["counted"] += 1
        _bump(d["met"], finding.reason)
    elif finding.outcome == "uncertain":
        c["uncertain"] += 1
        _bump(d["uncertain"], finding.reason)
    else:
        c["skipped"] += 1
        d["no_threat" if finding.outcome == "no_threat" else "skipped"] += 1
    return finding.outcome, tid


def analyse_game(pgn: str, user_color: str, analyser, types=TYPES) -> dict[str, dict]:
    """Run the detectors for `types` over every player move from each type's first ply. Returns {type: counts}.

    `analyser` is an `EvidenceAnalyser` (or a scripted stand-in with `analyse(board, depth=None)` and `.config`). M3 also gets
    the position before the opponent's last move (for its origin label), and M1's finding on the same move for `also_m1`.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or game.errors:
        raise ValueError("the PGN could not be read")
    white = user_color == "white"
    out = {t: _empty(t) for t in types}
    board = game.board()
    before_opponent: chess.Board | None = None
    last_m3: tuple[str, str | None] | None = None  # (outcome, threat move) of the previous player move
    for ply, node in enumerate(game.mainline()):
        move = node.move
        if (ply % 2 == 0) == white:
            m1_finding = None
            for t in types:
                if ply < first_ply(t):
                    continue
                if t == "M3":
                    finding = DETECTORS["M3"].detect(board, move, ply, analyser, previous=before_opponent)
                    if finding.outcome == "missed" and m1_finding is None and ply >= R.MIN_PLY:
                        m1_finding = DETECTORS["M1"].detect(board, move, ply, analyser)
                    last_m3 = _count_m3(out[t], finding, ply, last_m3, m1_finding)
                else:
                    finding = DETECTORS[t].detect(board, move, ply, analyser)
                    if t == "M1":
                        m1_finding = finding
                    _count(out[t], finding, ply)
        else:
            before_opponent = board.copy(stack=False)
        board.push(move)
    return out


def store_game(conn: sqlite3.Connection, game_id: str, result: dict[str, dict], config_id: str) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with transaction(conn):
        for t, c in result.items():
            details = json.dumps(c["details"], sort_keys=True) if "details" in c else None
            conn.execute(
                "INSERT OR IGNORE INTO realgame_game (game_id, mistake_type, detector_version, engine_config_id, player_moves,"
                " counted, events, uncertain, skipped, event_plies_json, rates_version, computed_at, details_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (game_id, t, detector_tag(t), config_id, c["player_moves"], c["counted"], c["events"], c["uncertain"],
                 c["skipped"], json.dumps(c["event_plies"]), RATES_VERSION, now, details),
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


def games_to_analyse(conn: sqlite3.Connection, types=TYPES) -> list[str]:
    """Every game in a frozen window or after a freeze, for any of `types` (a game is checked once for all of them)."""
    return list(games_by_type(conn, types))


def games_by_type(conn: sqlite3.Connection, types=TYPES) -> dict[str, set[str]]:
    """{game id: the types whose windows (baseline or post) hold that game}, in window order."""
    out: dict[str, set[str]] = {}
    for t in types:
        for w in realgame.frozen_windows(conn, t):
            for g in [*w["game_ids"], *post_game_ids(conn, t, w["time_control"])]:
                out.setdefault(g, set()).add(t)
    return out


def done_types(conn: sqlite3.Connection, config_id: str) -> dict[str, set[str]]:
    """{game id: the types with a current-version row under this engine config}."""
    tags = current_tags()
    rows = conn.execute(
        "SELECT game_id, mistake_type, detector_version FROM realgame_game WHERE engine_config_id = ?", (config_id,))
    have: dict[str, set[str]] = {}
    for r in rows:
        if tags.get(r["mistake_type"]) == r["detector_version"]:
            have.setdefault(r["game_id"], set()).add(r["mistake_type"])
    return have


def done_games(conn: sqlite3.Connection, config_id: str, types=TYPES) -> set[str]:
    """Games with a current-version row for every one of `types` under this engine config."""
    return {g for g, ts in done_types(conn, config_id).items() if set(types) <= ts}


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
    out = {
        "games_in_window": len(ids), "games": games, "missing_games": len(ids) - games,
        "player_moves": sum(r["player_moves"] for r in mine),
        "denominator": counted, "events": events, "uncertain": sum(r["uncertain"] for r in mine),
        "skipped": sum(r["skipped"] for r in mine),
        "rate": events / counted * scale if counted else None,
        "interval": None if interval is None else [interval[0] * scale, interval[1] * scale],
    }
    if mtype == "M3":
        out["details"] = _sum_details([json.loads(r["details_json"]) for r in mine if r["details_json"]])
    return out


def _sum_details(items: list[dict]) -> dict:
    """Add up M3 `details_json` dicts: numbers are summed, nested {reason: count} dicts are summed key by key."""
    total: dict = {}
    for d in items:
        for k, v in d.items():
            if isinstance(v, dict):
                sub = total.setdefault(k, {})
                for kk, n in v.items():
                    sub[kk] = sub.get(kk, 0) + n
            else:
                total[k] = total.get(k, 0) + v
    return total


def _comparison(mtype: str, before: dict, after: dict) -> dict:
    floor_unit = "games" if mtype == "M1" else "opportunities"
    have = (lambda w: w["games"]) if mtype == "M1" else (lambda w: w["denominator"])
    floor = FLOOR_GAMES if mtype == "M1" else FLOOR_OPPORTUNITIES
    out = {"floor": floor, "floor_unit": floor_unit, "baseline_has": have(before), "post_has": have(after)}
    incomplete = before["missing_games"] or after["missing_games"]
    if incomplete:
        return {**out, "state": "analysis_incomplete"}
    if not before["denominator"] or not after["denominator"]:  # games alone can pass the M1 floor with nothing to count
        return {**out, "state": "not_enough_data", "reason": "no_countable_moves"}
    if have(before) < floor or have(after) < floor:
        return {**out, "state": "not_enough_data", "reason": "below_floor"}
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


def rates(conn: sqlite3.Connection, types=TYPES) -> dict:
    """The Progress screen's real-game section: per type, per time control, both windows with their denominators.

    The screen asks for the default (M1 and M2); M3 is added only when asked (`report --types M3`).
    """
    tags = current_tags()
    out_types, configs = [], set()
    for t in types:
        windows = realgame.frozen_windows(conn, t)
        entry: dict = {"mistake_type": t, "label": TYPE_LABELS[t], "detector": tags[t], "unit": UNITS[t]}
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
            "engine_config_ids": sorted(configs), "min_ply": R.MIN_PLY,
            **({"m3_min_ply": R.M3_MIN_PLY} if "M3" in types else {}), "types": out_types}


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
        result = analyse_game(task["pgn"], task["user_color"], analyser, tuple(task["types"]))
        error = None
    except ValueError as e:  # one unreadable game must not stop the pass; it stays missing and the rates say so
        result, error = None, f"{type(e).__name__}: {e}"
    return {"game": task["game"], "result": result, "error": error, "config_id": analyser.config.id,
            "seconds": time.monotonic() - started}


def todo(conn: sqlite3.Connection, config_id: str, types=TYPES) -> tuple[list[tuple[str, tuple[str, ...]]], int, int]:
    """(game id, the types still to check for it) for every game in a window of `types`; plus the totals in and done."""
    wanted = games_by_type(conn, types)
    have = done_types(conn, config_id)
    out = []
    for gid, ts in wanted.items():
        missing = tuple(t for t in RATE_TYPES if t in ts and t not in have.get(gid, set()))
        if missing:
            out.append((gid, missing))
    return out, len(wanted), len(wanted) - len(out)


def run(workers: int, limit: int | None = None, types=TYPES) -> dict:
    db_path = default_path()
    conn = connect(db_path)
    added = pools.import_games(conn, games_path(), config.case_study_time_controls())
    from app.engine.evidence import open_evidence

    with open_evidence(conn) as probe:  # the config id of this engine, to know what is already done
        config_id = probe.config.id
    for t in types:
        if not realgame.frozen_windows(conn, t):
            hint = " (run `freeze` first)" if t == "M3" else " (frozen by its first practice session)"
            print(f"{t} has no frozen window yet{hint}: nothing to check for it", flush=True)
    pending, in_windows, already = todo(conn, config_id, types)
    if limit:
        pending = pending[:limit]
    tasks = []
    for gid, missing in pending:
        r = conn.execute("SELECT pgn, user_color FROM game WHERE id = ?", (gid,)).fetchone()
        tasks.append({"game": gid, "pgn": r["pgn"], "user_color": r["user_color"], "types": list(missing)})
    print(f"{added} games imported; {in_windows} games in the {'/'.join(types)} windows, {already} already done, "
          f"{len(tasks)} to check at {config_id}; {workers} engine processes", flush=True)
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
    return {"imported": added, "checked": done, "failed": len(failed), "engine_config_id": config_id, "types": list(types)}


def freeze(conn: sqlite3.Connection, mistake_type: str = "M3", *, now: datetime | None = None) -> dict:
    """Freeze the M3 window once: the last WINDOW_GAMES games per time control before now (ADR 0011).

    Imports the synced games first, so the window holds the latest games in `data/games/` (run `python -m app.sync` before
    this). Freezing again returns the window already frozen; nothing is ever replaced. Only M3 is frozen here: M1 and M2 are
    frozen by their first practice session.
    """
    if mistake_type != "M3":
        raise ValueError("only M3 is frozen by this command; M1 and M2 are frozen by their first practice session")
    already = realgame.frozen_windows(conn, mistake_type)
    added = 0 if already else pools.import_games(conn, games_path(), config.case_study_time_controls())
    windows = realgame.freeze_baseline_window(conn, mistake_type, now=now)
    return {"mistake_type": mistake_type, "imported": added, "already_frozen": bool(already),
            "windows": [{"time_control": w["time_control"], "games": len(w["game_ids"]), "frozen_at": w["frozen_at"]}
                        for w in windows]}


def status(conn: sqlite3.Connection) -> dict:
    out = {"rates_version": RATES_VERSION, "detectors": current_tags(), "types": {}}
    for t in RATE_TYPES:
        ws = realgame.frozen_windows(conn, t)
        out["types"][t] = [{"time_control": w["time_control"], "frozen_at": w["frozen_at"],
                            "baseline_games": len(w["game_ids"]),
                            "post_games": len(post_game_ids(conn, t, w["time_control"]))} for w in ws] or "not started"
    rows = conn.execute("SELECT engine_config_id, COUNT(DISTINCT game_id) AS n FROM realgame_game GROUP BY 1").fetchall()
    out["games_checked_by_config"] = {r["engine_config_id"]: r["n"] for r in rows}
    out["games_to_check"] = len(games_to_analyse(conn, RATE_TYPES))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.learner.realgame_rates")
    sub = p.add_subparsers(dest="cmd", required=True)
    types_help = "comma-separated mistake types, e.g. M3 or M1,M2,M3 (default M1,M2)"
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--limit", type=int, default=None, help="only the first N games still to check (to try it out)")
    r.add_argument("--types", default=None, help=types_help)
    sub.add_parser("status")
    rep = sub.add_parser("report")
    rep.add_argument("--types", default=None, help=types_help)
    sub.add_parser("freeze", help="freeze the M3 window once (last 30 games per time control); never replaces one")
    args = p.parse_args(argv)
    if args.cmd == "run":
        print(json.dumps(run(args.workers, args.limit, parse_types(args.types)), indent=1))
    elif args.cmd == "status":
        print(json.dumps(status(connect()), indent=1))
    elif args.cmd == "freeze":
        print(json.dumps(freeze(connect()), indent=1))
    else:
        print(json.dumps(rates(connect(), parse_types(args.types)), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
