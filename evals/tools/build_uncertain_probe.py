"""Probe for the M3 `uncertain` outcomes (`threat_unavoidable`, `loss_not_from_threat`). Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/build_uncertain_probe.py build|run [--pgn PATH]

Not a frozen eval set and not a score: engine-labelled, no person has checked it, and the label rules below are the builder's own idea of
the two cases. It answers "what does `missed_threat` v3 do on positions where it should abstain?" with counts, nothing more.
Writes evals/sets/m3_uncertain_probe/ (positions.jsonl, provenance.json, result.json).

Groups:
- `unavoidable` (built here from Lichess games not used by missed_threat_v3 or v4): calm position, player to move, not in check; the opponent
  has a static threat T after a pass (capture_net >= 2 or mate in one); passing costs less than 100 cp (the best move does not escape it
  either); and after the engine's best move B, T is still legal and still wins by the exchange count. Expected detector outcome: uncertain /
  threat_unavoidable. The move played is the player's real move.
- `not_from_threat` (the 15 `uncertain` candidates of missed_threat_v3: loss of 300+ cp, T legal and still winning after the move, forced-threat
  loss under 100 cp; engine-labelled, pins not seen). Expected: uncertain / loss_not_from_threat, though the builder cannot see pins.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import chess
import chess.pgn

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_missed_threat_set as V
from build_real_play_set import Engine

ROOT = V.ROOT
OUT = ROOT / "evals" / "sets" / "m3_uncertain_probe"
SEED = 20261103
QUOTA = 20
CALM, MAX_PASS_COST = 400, 100


def classify(engine, board):
    if not V.usable(board):
        return None
    P = V.passed(board)
    threats = V.static_threats(P)
    if not threats:
        return None
    F = V.Facts(engine, board)
    if abs(F.best_cp) > CALM or F.threat_cp >= MAX_PASS_COST:
        return None
    B = chess.Move.from_uci(F.best.pv[0])
    after = board.copy()
    after.push(B)
    still = [t for t in threats if t in after.legal_moves and V.wins(after, t)]
    if not still:
        return None
    return {"best_cp": F.best_cp, "pass_cost_cp": F.threat_cp, "best_move": B.uci(), "threats": [t.uci() for t in still]}


def build(pgn):
    used = set()
    for name in ("missed_threat_v3", "missed_threat_v4"):
        used |= {json.loads(x)["game"] for x in (ROOT / "evals" / "sets" / name / "candidates.jsonl").read_text().splitlines()}
    games = []
    with open(pgn) as f:
        while (g := chess.pgn.read_game(f)) is not None:
            if g.headers.get("Site", "") not in used:
                games.append(g)
    rng = random.Random(SEED)
    rng.shuffle(games)
    items = []
    with Engine() as engine:
        for g in games:
            if len(items) >= QUOTA:
                break
            moves = list(g.mainline_moves())
            for p in rng.sample(range(V.MIN_PLY, max(V.MIN_PLY + 1, len(moves) - 1)), min(12, max(0, len(moves) - 1 - V.MIN_PLY))):
                b = g.board()
                for m in moves[:p]:
                    b.push(m)
                b = chess.Board(b.fen())
                r = classify(engine, b)
                if r:
                    items.append({"id": f"up-{len(items) + 1:03d}", "group": "unavoidable", "expected": "uncertain:threat_unavoidable",
                                  "fen": b.fen(), "move_uci": moves[p].uci(), "move_san": b.san(moves[p]), "ply": p,
                                  "game": g.headers.get("Site", ""), **r})
                    break
        name = engine.name
    v3 = ROOT / "evals" / "sets" / "missed_threat_v3" / "uncertain_unverified.jsonl"
    for x in map(json.loads, v3.read_text().splitlines()):
        items.append({"id": f"up-{len(items) + 1:03d}", "group": "not_from_threat", "expected": "uncertain:loss_not_from_threat",
                      "fen": x["fen"], "move_uci": x["move_uci"], "move_san": x["move_san"], "ply": x["ply"], "game": x["game"],
                      "best_cp": x["best_cp"], "loss_cp": x["loss_cp"], "ftl_cp": x.get("ftl_cp")})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "positions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in items))
    counts = {}
    for r in items:
        counts[r["group"]] = counts.get(r["group"], 0) + 1
    (OUT / "provenance.json").write_text(json.dumps({"seed": SEED, "engine": name, "oracle_depth": V.ORACLE.depth, "counts": counts,
                                                    "games_file": pgn.name, "frozen": False, "checked_by_person": False}, indent=2) + "\n")
    print(counts)


def run():
    sys.path.insert(0, str(ROOT / "backend"))
    from app.db.schema import connect
    from app.detectors import missed_threat
    from app.engine.evidence import open_evidence

    rows = [json.loads(x) for x in (OUT / "positions.jsonl").read_text().splitlines()]
    out = []
    with open_evidence(connect(str(ROOT / "evals" / "runs" / "m3_uncertain_probe_cache.sqlite3"))) as an:
        for r in rows:
            f = missed_threat.detect(chess.Board(r["fen"]), chess.Move.from_uci(r["move_uci"]), r["ply"], an)
            out.append({"id": r["id"], "group": r["group"], "expected": r["expected"], "got": f"{f.outcome}:{f.reason}"})
    summary = {}
    for g in ("unavoidable", "not_from_threat"):
        rs = [o for o in out if o["group"] == g]
        dist = {}
        for o in rs:
            dist[o["got"]] = dist.get(o["got"], 0) + 1
        summary[g] = {"n": len(rs), "expected": rs[0]["expected"] if rs else None,
                      "as_expected": sum(o["got"] == o["expected"] for o in rs), "outcomes": dist}
    (OUT / "result.json").write_text(json.dumps({"detector_version": missed_threat.VERSION, "summary": summary, "items": out}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "run"])
    ap.add_argument("--pgn", default=str(ROOT / "data" / "lichess" / "rapid_600_1200_2026-09_b.pgn"))
    a = ap.parse_args()
    build(Path(a.pgn)) if a.mode == "build" else run()
