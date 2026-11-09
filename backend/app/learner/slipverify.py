"""Deeper engine check of first-slip drills (ADR 0020): does each slip, and its answer set, hold at a much deeper search?

  uv run python -m app.learner.slipverify sample [--depth 24]   # the 30 hand-check positions (gate: 27 of 30 slips hold)
  uv run python -m app.learner.slipverify all [--depth 24]      # every first-slip drill (resumable)
  uv run python -m app.learner.slipverify report                # rates with denominators
  uv run python -m app.learner.slipverify exclude [--depth 24]  # keep drills whose slip did not hold out of the rounds (slip_excluded_v1.json)

The drills were confirmed at depth 18, MultiPV 3. A player under 1000 cannot judge an engine by eye, so the check is the engine itself
at a deeper search, run from scratch (hash cleared). A slip *holds* when the deeper search still loses at least SLIP_LOSS_CP for the
mover (a position that is decided at the deeper search is noted, not failed). The answers *hold* when the deeper best move is one of the drill's accepted moves. This is a
second engine opinion at higher depth, not a proof. Imports no LLM code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import chess

from app.engine.stockfish import Budget
from app.learner import drillbank, slipfinder, slipround

DEPTH = 24
MATE_CP = 10_000
GATE = 27
SAMPLE_SIZE = 30
SAMPLE_SALT = "slipcheck-v1"  # the salt of the first sample (2026-11-09); keeping it keeps those 30 positions


def _cp(score) -> int:
    if score.mate is not None:
        return MATE_CP if score.mate_sign == 1 else -MATE_CP
    return score.cp


def verify(drill: dict, engine, depth: int = DEPTH) -> dict:
    """One drill at `depth`: the deeper loss of the played move and whether the deeper best move is an accepted answer."""
    board = chess.Board(drill["fen"])
    mover = board.turn
    budget = Budget(depth=depth)
    top = engine.analyse_multi(board, 3, budget, perspective=mover, new_game=True)
    after = board.copy(stack=False)
    after.push(chess.Move.from_uci(drill["played"]))
    played_cp = _cp(engine.analyse(after, budget, perspective=mover).score)
    best_cp = _cp(top[0].score)
    loss = best_cp - played_cp
    slip_holds = loss >= slipfinder.SLIP_LOSS_CP  # a position decided at depth is noted, not failed: a big loss from it is still a slip
    decided = abs(best_cp) >= slipfinder.DECIDED_CP
    answers_hold = top[0].best_move in drill["accepted"]
    verdict = "slip_not_confirmed" if not slip_holds else ("holds" if answers_hold else "slip_holds_answers_differ")
    return {"id": drill["id"], "game_id": drill["game_id"], "depth": depth, "best_cp": best_cp, "played_cp": played_cp, "loss_cp": loss,
            "deep_best": top[0].best_move, "slip_holds": slip_holds, "decided_deep": decided, "answers_hold": answers_hold, "verdict": verdict}


def summarise(rows: list[dict], gate: int | None = None, expected: int | None = None) -> dict:
    out = {"of": len(rows), "slip_holds": sum(r["slip_holds"] for r in rows), "answers_hold": sum(r["answers_hold"] for r in rows),
           "slip_not_confirmed": [r["id"] for r in rows if not r["slip_holds"]],
           "answers_differ": [r["id"] for r in rows if r["slip_holds"] and not r["answers_hold"]]}
    if gate is not None:
        out["gate"] = gate
        out["passed"] = len(rows) == expected and out["slip_holds"] >= gate
    return out


def excluded_path() -> Path:
    return slipround.excluded_path()


def exclusions(rows: list[dict]) -> dict[str, dict]:
    """The drills whose slip did not hold at the deeper search, with the reason."""
    return {r["id"]: {"reason": f"{r['verdict']}_at_depth_{r['depth']}"} for r in rows if not r["slip_holds"]}


def _saved_exclusions() -> dict[str, dict]:
    try:
        raw = json.loads(excluded_path().read_text())
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_exclusions(excluded: dict[str, dict]) -> None:
    path = excluded_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(excluded, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, path)  # a reader sees the old file or the new one, never half of one


def results_path(depth: int) -> Path:
    return drillbank.bank_dir() / f"slipverify_v1_d{depth}.jsonl"


def _load(depth: int) -> dict[str, dict]:
    p = results_path(depth)
    return {r["id"]: r for r in map(json.loads, p.read_text().splitlines())} if p.exists() else {}


def run(drills: list[dict], depth: int) -> list[dict]:
    from app.engine.stockfish import Engine

    done = _load(depth)
    with Engine(options={"Hash": 256, "Threads": 4}) as engine, results_path(depth).open("a") as f:
        for n, d in enumerate((d for d in drills if d["id"] not in done), 1):
            row = verify(d, engine, depth)
            done[d["id"]] = row
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(n, row["id"], row["verdict"], row["loss_cp"], flush=True)
    return [done[d["id"]] for d in drills]


def _order(drill: dict) -> str:
    return hashlib.sha256(f"{SAMPLE_SALT}|{drill['id']}".encode()).hexdigest()


def sample(drills: list[dict], n: int = SAMPLE_SIZE) -> list[dict]:
    """`n` own drills by hash order, never two from one game, so the choice does not depend on the order of the bank."""
    out, used = [], set()
    for d in sorted((d for d in drills if d["source"] == "own"), key=_order):
        if d["game_id"] not in used:
            used.add(d["game_id"])
            out.append(d)
        if len(out) == n:
            break
    return out


def sample_drills() -> list[dict]:
    return sample(slipround.read_slips())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "all", "report", "exclude"])
    ap.add_argument("--depth", type=int, default=DEPTH)
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        rows = run(sample_drills(), a.depth)
        print(json.dumps(summarise(rows, GATE, SAMPLE_SIZE), indent=1))
    elif a.cmd == "all":
        run([d for d in slipround.read_slips() if d["source"] == "own"], a.depth)
    elif a.cmd == "exclude":  # keep the drills that failed the deeper check out of the rounds (a reversible list, the drill file is not touched)
        save_exclusions({**_saved_exclusions(), **exclusions(list(_load(a.depth).values()))})
    print(json.dumps(summarise(list(_load(a.depth).values())), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
