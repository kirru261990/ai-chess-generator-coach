"""Deeper engine check of first-slip drills (ADR 0020): does each slip, and its answer set, hold at a much deeper search?

  uv run python -m app.learner.slipverify sample [--depth 24]   # the 30 hand-check positions (gate: 27 of 30 slips hold)
  uv run python -m app.learner.slipverify all [--depth 24]      # every first-slip drill (resumable)
  uv run python -m app.learner.slipverify report                # rates with denominators

The drills were confirmed at depth 18, MultiPV 3. A player under 1000 cannot judge an engine by eye, so the check is the engine itself
at a deeper search, run from scratch (hash cleared). A slip *holds* when the deeper search still loses at least SLIP_LOSS_CP for the
mover (a position that is decided at the deeper search is noted, not failed). The answers *hold* when the deeper best move is one of the drill's accepted moves. This is a
second engine opinion at higher depth, not a proof. Imports no LLM code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chess

from app.engine.stockfish import Budget
from app.learner import drillbank, slipcheck, slipfinder, slipround

DEPTH = 24
MATE_CP = 10_000
GATE = 27


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


def sample_drills() -> list[dict]:
    by_id = {d["id"]: d for d in slipround.read_slips()}
    key = json.loads(slipcheck.key_path().read_text())
    return [by_id[i["drill_id"]] for i in key["items"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "all", "report"])
    ap.add_argument("--depth", type=int, default=DEPTH)
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        rows = run(sample_drills(), a.depth)
        print(json.dumps(summarise(rows, GATE, 30), indent=1))
    elif a.cmd == "all":
        run([d for d in slipround.read_slips() if d["source"] == "own"], a.depth)
    print(json.dumps(summarise(list(_load(a.depth).values())), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
