"""Build the PRD v2 position store from the synced games (Step 1b; ADR 0006).

  uv run python -m app.learner.evidence_run run [--workers 4] [--limit N]   # import games, detect, store positions
  uv run python -m app.learner.evidence_run summary                          # counts by kind, type and pool

1. Synced case-study games (10|0, 15|10) are added to `game` with their pool (`pools.py`).
2. Candidates come from the stored depth-10 fast pass, so the depth-18 evidence engine only sees moves worth checking:
   - M1 / M2 candidates: the player's move from MIN_PLY on, the position not already far beyond DECIDED_LIMIT_CP, a loss of at
     least PREFILTER_LOSS_CP, and (M1) a piece of the player's left winnable for 2+ by static exchange after the move, or (M2)
     an opponent piece winnable for 2+ before it. The prefilter is looser than the PRD rules (loss 100 vs 150/200, material 2
     vs 3) so the evidence engine makes the decision. A candidate the prefilter drops is never seen: Step 1c reports that limit.
   - CLEAN candidates: up to CLEAN_TRIES per game whose fast-pass loss is below CLEAN_MAX_LOSS_CP and which pass the static
     CLEAN checks, in a fixed pseudo-random order; the first one the evidence engine confirms is kept (at most one per game).
3. Each MISTAKE position stores its evidence record and its verified alternatives (the top engine moves that are sound).
4. A summary (outcome and reason counts, timings, config, pool counts) is written to `data/evidence/` (git-ignored).

Results for rejected candidates are not stored as positions, but their engine searches are cached, so a re-run is fast and
gives the same answer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import chess

from app import config
from app.db.schema import connect, default_path
from app.detectors import clean, hanging_own_v3, missed_free_v3
from app.detectors import prd_rules as R
from app.detectors.hanging_own import hanging_pieces
from app.detectors.missed_free import free_pieces
from app.engine.batch import SCHEMA, game_id
from app.learner import pools
from app.learner.review import rank_for_mover

PREFILTER_LOSS_CP = 100
PREFILTER_DECIDED_CP = 700  # a little looser than DECIDED_LIMIT_CP: depth 10 and depth 18 differ
PREFILTER_MATERIAL = 2
CLEAN_TRIES = 3
DETECTORS = {"M1": hanging_own_v3, "M2": missed_free_v3}


def detector_tag(module) -> str:
    return f"{module.DETECTOR}@{module.VERSION}+rules{R.RULES_VERSION}"


def games_path() -> Path:
    return config.DATA_DIR / "games" / f"chesscom_{config.chesscom_username()}.jsonl"


def analysis_path() -> Path:
    return config.DATA_DIR / "analysis" / f"chesscom_{config.chesscom_username()}.jsonl"


def candidates(analysis: dict, white: bool, platform_id: str) -> tuple[list[dict], list[dict]]:
    """(mistake candidates, clean candidates in try order) for one game's fast pass."""
    mistakes, cleans = [], []
    positions = analysis["positions"]
    for ply, uci in enumerate(analysis["moves"]):
        if (ply % 2 == 0) != white or ply < R.MIN_PLY:
            continue
        before, after = rank_for_mover(positions[ply], white), rank_for_mover(positions[ply + 1], white)
        if abs(before) > PREFILTER_DECIDED_CP:
            continue
        board = chess.Board(positions[ply]["fen"])
        move = chess.Move.from_uci(uci)
        loss = before - after
        if loss >= PREFILTER_LOSS_CP:
            types = []
            board.push(move)
            if any(h.gain >= PREFILTER_MATERIAL for h in hanging_pieces(board, not board.turn)):
                types.append("M1")
            board.pop()
            if any(f.gain >= PREFILTER_MATERIAL for f in free_pieces(board)):
                types.append("M2")
            if types:
                mistakes.append({"ply": ply, "fen": board.fen(), "move": uci, "types": types})
        elif loss < R.CLEAN_MAX_LOSS_CP and clean.static_reason(board) is None:
            cleans.append({"ply": ply, "fen": board.fen(), "move": uci})
    def order(c: dict) -> str:
        return hashlib.sha256(f"{platform_id}:{c['ply']}".encode()).hexdigest()

    return mistakes, sorted(cleans, key=order)[:CLEAN_TRIES]


# --- worker side: one pinned engine per process --------------------------------------------------------------------------

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
    found, outcomes = [], []
    for cand in task["mistakes"]:
        board = chess.Board(cand["fen"])
        move = chess.Move.from_uci(cand["move"])
        for mtype in cand["types"]:
            finding = DETECTORS[mtype].detect(board, move, cand["ply"], analyser)
            outcomes.append((mtype, finding.outcome, finding.reason))
            if finding.evidence is not None:
                found.append({"kind": "MISTAKE", "type": mtype, "ply": cand["ply"], "fen": cand["fen"],
                              "move": cand["move"], "evidence": finding.evidence,
                              "alternatives": list(finding.alternatives)})
    for cand in task["cleans"]:
        finding = clean.detect(chess.Board(cand["fen"]), chess.Move.from_uci(cand["move"]), cand["ply"], analyser)
        outcomes.append(("CLEAN", finding.outcome, finding.reason))
        if finding.evidence is not None:
            found.append({"kind": "CLEAN", "type": None, "ply": cand["ply"], "fen": cand["fen"],
                          "move": cand["move"], "evidence": finding.evidence, "alternatives": None})
            break
    return {"game": task["game"], "pool": task["pool"], "found": found, "outcomes": outcomes,
            "config_id": analyser.config.id, "seconds": time.monotonic() - started}


# --- main side --------------------------------------------------------------------------------------------------------

def fast_pass_by_game() -> dict[str, dict]:
    """Stored fast-pass records by Chess.com game id (the latest line per game wins, as in `AnalysisStore`)."""
    out = {}
    path = analysis_path()
    if path.exists():
        with path.open() as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    out[game_id(r["source_id"])] = r
    return out


def build_tasks(conn, limit: int | None) -> list[dict]:
    analyses = fast_pass_by_game()
    tasks = []
    rows = conn.execute(
        "SELECT id, platform_id, pool, user_color FROM game WHERE user_color IS NOT NULL ORDER BY played_at DESC"
    ).fetchall()
    for row in rows:
        analysis = analyses.get(row["platform_id"])
        if analysis is None or analysis.get("schema") != SCHEMA:
            continue
        mistakes, cleans = candidates(analysis, row["user_color"] == "white", row["platform_id"])
        if mistakes or cleans:
            tasks.append({"game": row["id"], "pool": row["pool"], "mistakes": mistakes, "cleans": cleans})
        if limit and len(tasks) >= limit:
            break
    return tasks


def store_positions(conn, result: dict) -> int:
    added = 0
    for f in result["found"]:
        module = DETECTORS[f["type"]] if f["kind"] == "MISTAKE" else clean
        cur = conn.execute(
            "INSERT OR IGNORE INTO position (game_id, ply, fen, kind, mistake_type, source_tag, pool, original_move,"
            " evidence_json, verified_alternatives_json, engine_config_id, detector_version)"
            " VALUES (?, ?, ?, ?, ?, 'chesscom', ?, ?, ?, ?, ?, ?)",
            (result["game"], f["ply"], f["fen"], f["kind"], f["type"], result["pool"], f["move"],
             json.dumps(f["evidence"]), None if f["alternatives"] is None else json.dumps(f["alternatives"]),
             result["config_id"], detector_tag(module)),
        )
        added += cur.rowcount
    return added


def run(workers: int, limit: int | None) -> dict:
    db_path = default_path()
    conn = connect(db_path)
    added_games = pools.import_games(conn, games_path(), config.case_study_time_controls())
    tasks = build_tasks(conn, limit)
    n_mistake = sum(len(c["types"]) for t in tasks for c in t["mistakes"])
    n_clean = sum(len(t["cleans"]) for t in tasks)
    print(f"{added_games} games imported; {len(tasks)} games with candidates: {n_mistake} mistake checks, "
          f"{n_clean} clean candidates; {workers} engine processes", flush=True)
    started = time.monotonic()
    outcomes: Counter = Counter()
    reasons: Counter = Counter()
    added = 0
    config_id = None
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, initializer=_init_worker, initargs=(str(db_path),)) as pool:
        for i, result in enumerate(pool.imap_unordered(_process, tasks), 1):
            config_id = result["config_id"]
            added += store_positions(conn, result)
            for kind, outcome, reason in result["outcomes"]:
                outcomes[f"{kind}:{outcome}"] += 1
                reasons[f"{kind}:{outcome}:{reason}"] += 1
            if i % 25 == 0 or i == len(tasks):
                elapsed = time.monotonic() - started
                print(f"  {i}/{len(tasks)} games, {added} positions stored, {elapsed / 60:.1f} min", flush=True)
    summary = {
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "engine_config_id": config_id,
        "rules_version": R.RULES_VERSION,
        "detectors": {k: detector_tag(m) for k, m in DETECTORS.items()} | {"CLEAN": detector_tag(clean)},
        "prefilter": {"loss_cp": PREFILTER_LOSS_CP, "decided_cp": PREFILTER_DECIDED_CP,
                      "material": PREFILTER_MATERIAL, "clean_tries": CLEAN_TRIES},
        "workers": workers,
        "minutes": round((time.monotonic() - started) / 60, 1),
        "games_with_candidates": len(tasks),
        "checks": {"mistake": n_mistake, "clean_candidates": n_clean},
        "outcomes": dict(sorted(outcomes.items())),
        "reasons": dict(sorted(reasons.items())),
        "positions_added": added,
        "pool_counts": pools.pool_counts(conn),
        "positions": position_counts(conn),
    }
    out = config.DATA_DIR / "evidence" / f"run_{datetime.now(UTC):%Y%m%dT%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1) + "\n")
    print(f"summary: {out}")
    return summary


def position_counts(conn) -> dict:
    out: dict = {}
    for row in conn.execute(
        "SELECT kind, IFNULL(mistake_type, '-') AS t, pool, COUNT(*) AS n FROM position GROUP BY kind, t, pool"
    ):
        out.setdefault(f"{row['kind']}:{row['t']}", {})[row["pool"]] = row["n"]
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.learner.evidence_run")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--limit", type=int, default=None, help="only the N most recent games with candidates")
    sub.add_parser("summary")
    args = p.parse_args(argv)
    if args.cmd == "run":
        summary = run(args.workers, args.limit)
        print(json.dumps({k: summary[k] for k in ("minutes", "outcomes", "positions")}, indent=1))
    else:
        conn = connect()
        print(json.dumps({"games": pools.pool_counts(conn), "positions": position_counts(conn)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
