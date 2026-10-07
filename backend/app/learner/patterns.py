"""The pattern layer (T14): run the detectors over the user's moves and report miss rates.

For each user move: the board before it, the move, and `Evidence` built from the stored fast pass (depth 10,
White's view, converted to the mover's side with `review.rank_for_mover`). Each detector gives
taken / missed / uncertain / not_applicable.

Rates (AGENTS rules 3 and 5):
- uncertain moves are excluded from every numerator and denominator and reported separately
- `missed_free`: missed / (taken + missed), and missed per 100 moves
- `hanging_own`: missed per 100 moves only (its opportunity holds in most positions, so missed/available is not
  meaningful; the count is still reported)
- labels follow spec C3: "tentative" at >= 3 misses across >= 2 games; "established" when, in addition, there are
  >= 8 opportunities (taken + missed); otherwise "insufficient"
- 95% Wilson intervals treat moves as independent. They are not (moves in one game are related), so the intervals
  are optimistic; the label and the sample sizes matter more than the interval.

Results are grouped by time control (no pooled figure; ADR 0002). Game ids and examples stay in `data/` only.

  uv run python -m app.learner.patterns baseline   # the frozen 100-game window -> data/patterns/
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import chess

from app import config
from app.detectors import hanging_own, missed_free
from app.detectors.hanging_own import Evidence
from app.engine.batch import BATCH_BUDGET, SCHEMA, game_id
from app.learner import baseline
from app.learner.review import rank_for_mover

DETECTORS = {"hanging_own": hanging_own, "missed_free": missed_free}
OUTCOMES = ("taken", "missed", "uncertain", "not_applicable")
MIN_MISSES, MIN_GAMES, MIN_OPPORTUNITIES = 3, 2, 8  # spec C3 (configurable product rules)
RESULTS_VERSION = 1


class PatternError(Exception):
    pass


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for k successes in n trials (None if n == 0)."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def user_moves(analysis: dict, user_color: str):
    """(ply, board before, move, evidence) for each of the user's moves. Evidence is from the fast pass."""
    white = user_color == "white"
    positions = analysis["positions"]
    for ply, uci in enumerate(analysis["moves"]):
        if (ply % 2 == 0) != white:
            continue
        before, after = positions[ply], positions[ply + 1]
        board = chess.Board(before["fen"])
        move = chess.Move.from_uci(uci)
        evidence = Evidence(rank_for_mover(before, white), rank_for_mover(after, white))
        yield ply, board, move, evidence


def classify_game(game: dict, analysis: dict) -> list[dict]:
    """One record per user move: its ply and each detector's outcome."""
    if analysis.get("schema") != SCHEMA:
        raise PatternError(f"analysis schema {analysis.get('schema')} is not the current {SCHEMA}")
    rows = []
    for ply, board, move, evidence in user_moves(analysis, game["user_color"]):
        row = {"ply": ply, "outcomes": {}}
        for name, detector in DETECTORS.items():
            row["outcomes"][name] = detector.detect(board, move, evidence).outcome
        rows.append(row)
    return rows


def label(misses: int, games_with_miss: int, opportunities: int) -> str:
    if misses < MIN_MISSES or games_with_miss < MIN_GAMES:
        return "insufficient"
    return "established" if opportunities >= MIN_OPPORTUNITIES else "tentative"


def summarise(per_game: list[list[dict]]) -> dict:
    """Aggregate classified games (one list of move rows per game) into per-detector figures."""
    n_moves = sum(len(rows) for rows in per_game)
    out = {"games": len(per_game), "user_moves": n_moves, "detectors": {}}
    for name, detector in DETECTORS.items():
        counts = dict.fromkeys(OUTCOMES, 0)
        games_with_miss = 0
        for rows in per_game:
            game_counts = [r["outcomes"][name] for r in rows]
            for o in game_counts:
                counts[o] += 1
            games_with_miss += "missed" in game_counts
        opportunities = counts["taken"] + counts["missed"]
        moves_counted = n_moves - counts["uncertain"]  # uncertain moves leave the denominator (rule 5)
        misses = counts["missed"]
        d = {
            "version": detector.VERSION,
            "counts": counts,
            "games_with_a_miss": games_with_miss,
            "opportunities": opportunities,
            "moves_counted": moves_counted,
            "missed_per_100_moves": _rate(misses, moves_counted, 100),
            "label": label(misses, games_with_miss, opportunities),
        }
        if name == "missed_free":
            d["missed_of_available"] = _rate(misses, opportunities, 1)
        out["detectors"][name] = d
    return out


def _rate(k: int, n: int, scale: int) -> dict | None:
    if n == 0:
        return None
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": k / n * scale, "ci95": [lo * scale, hi * scale]}


def run(games: list[dict], analyses: dict[str, dict], window: dict) -> dict:
    """Measure the window, per time control. Fails closed if a window game or its analysis is missing."""
    by_id = {game_id(g["source_id"]): g for g in games}
    result = {"results_version": RESULTS_VERSION, "window_sha256": window["sha256"], "by_time_control": {}}
    want = {"depth": BATCH_BUDGET.depth, "movetime_ms": BATCH_BUDGET.movetime_ms}
    engines = set()
    for tc_label, part in window["by_time_control"].items():
        classified = []
        for gid in part["ids"]:
            game = by_id.get(gid)
            if game is None:
                raise PatternError(f"window game {gid} is missing from the synced games")
            analysis = analyses.get(game["source_id"])
            if analysis is None:
                raise PatternError(f"window game {gid} has no fast-pass analysis")
            if analysis["budget"] != want:  # a shallow re-run must never mix into the baseline evidence
                raise PatternError(f"window game {gid} was analysed at {analysis['budget']}, expected {want}")
            engines.add(analysis["engine"])
            if len(engines) > 1:
                raise PatternError(f"window games were analysed by different engines: {sorted(engines)}")
            classified.append(classify_game(game, analysis))
        result["by_time_control"][tc_label] = summarise(classified)
    result["engine"] = {"name": next(iter(engines)), "budget": want}
    return result


def report(result: dict) -> str:
    lines = [
        (f"Baseline pattern results (fast-pass evidence: {result['engine']['name']}, "
         f"budget {result['engine']['budget']})"),
        "Per time control only. Uncertain moves are excluded from every rate.",
    ]
    for tc, s in result["by_time_control"].items():
        lines.append(f"\n{tc}: {s['games']} games, {s['user_moves']} of your moves")
        for name, d in s["detectors"].items():
            c = d["counts"]
            lines.append(
                f"  {name} v{d['version']} [{d['label']}]: taken {c['taken']}, missed {c['missed']}, "
                f"uncertain {c['uncertain']}, not applicable {c['not_applicable']}; "
                f"missed in {d['games_with_a_miss']} games"
            )
            if d.get("missed_of_available"):
                lines.append("    missed / available: " + _fmt(d["missed_of_available"], True))
            if d["missed_per_100_moves"]:
                lines.append("    missed per 100 moves: " + _fmt(d["missed_per_100_moves"], False))
    return "\n".join(lines)


def _fmt(r: dict, percent: bool) -> str:
    f = "{:.0%}" if percent else "{:.1f}"
    lo, hi = r["ci95"]
    return f"{r['k']}/{r['n']} = {f.format(r['rate'])} (95% interval {f.format(lo)} to {f.format(hi)})"


def _load_analyses(path: Path) -> dict[str, dict]:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["source_id"]] = r
    return out


def main(argv: list[str]) -> None:
    if argv != ["baseline"]:
        sys.exit(__doc__)
    username = config.chesscom_username()
    if not username:
        sys.exit("set CHESSCOM_USERNAME in .env")
    try:
        window = baseline.verify()  # never measure a window that does not match its record
        analyses = _load_analyses(config.DATA_DIR / "analysis" / f"chesscom_{username.lower()}.jsonl")
        result = run(baseline._games(), analyses, window)
    except (baseline.BaselineError, PatternError) as e:
        sys.exit(str(e))
    result["computed_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    out = config.DATA_DIR / "patterns" / "baseline_patterns_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(report(result))
    print(f"\nwritten to {out} (not frozen; T15 freezes the results)")


if __name__ == "__main__":
    main(sys.argv[1:])
