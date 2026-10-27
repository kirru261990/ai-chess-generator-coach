"""Build the M3 eval set `missed_threat_v2` (TASKS M3c2). Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/build_missed_threat_set_v2.py

v2 keeps the v1 design (build_missed_threat_set.py, LABEL_RULE.md there) and fixes the two flaws the v1 score showed
(evals/reports/missed_threat_v1_2026-10-26_notes.md): positions near the "decided" cut-off, and `met` items whose threat was only
an engine pass cost. An attempt to add `uncertain` ("unavoidable") items from puzzles and from random trapped-piece positions did not give
labels I trust (see LABEL_RULE.md), so v2 has as few `uncertain` items as v1. Puzzles used in v1 are not used again.
"""

import json
import random
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_missed_threat_set as V  # the v1 builder: helpers and constants; it imports no detectors

B = V.B
OUT = V.ROOT / "evals" / "sets" / "missed_threat_v2"
V1_SET = V.ROOT / "evals" / "sets" / "missed_threat_v1" / "positions.jsonl"
SEED = 20261027
CALM_CP = 400  # depth-14 score of the best move must be within this (v1: 600, which sat on the detector's cut-off)
CALM18_CP = 550  # and within this at depth 18, the detector's depth (its cut-off is 600)
DEEP = B.Budget(depth=18)
LINE_PLIES = 4  # an engine threat must win material or mate within this many plies

V.ADV = [  # v1's hand-built list, with the two positions that were beyond the new margin made calmer
    (fen.replace("r3k3/pp3ppp/8/3N4/8/8/PPP2PPP/4K3 b - - 0 15", "r3k3/pp3pp1/8/3N4/8/8/PPP2PPP/4K3 b - - 0 15")
        .replace("n5kr/5ppp/8/PN6/4B3/8/6PP/4K3 b - - 0 30", "n5kr/5ppp/8/PN6/4B3/8/7P/4K3 b - - 0 30"),
     "g7g6" if (fen.startswith("r3k3/pp3ppp") and uci == "h7h6") else uci, label, reason)
    for fen, uci, label, reason in V.ADV
]

V.QUOTA.clear()
V.QUOTA.update({"missed_real": 15, "met_real": 10, "constructed_missed": 10, "constructed_quiet": 5, "hung_not_threat": 5,
                "quiet_blunder": 4, "unavoidable": 0})
V.DECIDED_CP = CALM_CP


def calm(engine, board):
    """Not near the decided cut-off at either depth."""
    a = engine.analyse(board, DEEP, perspective=board.turn)
    return abs(V.cp(a)) <= CALM18_CP


def engine_line_wins(engine, pboard):
    """The engine's best line for the side to move in `pboard` mates or nets >= 2 pawns within LINE_PLIES (own tally)."""
    mover = pboard.turn
    a = engine.analyse(pboard, V.ORACLE, perspective=mover)
    walk, base = pboard.copy(), B.balance(pboard, mover)
    best = 0
    for i, u in enumerate(a.pv[:LINE_PLIES], 1):
        walk.push_uci(u)
        if walk.is_checkmate():
            return True
        if i % 2 == 0:
            best = max(best, B.balance(walk, mover) - base)
    return best >= V.MIN_GAIN


def concrete_threat(engine, board):
    """(static threats, concrete?) for the player to move in `board`: a static win, or an engine line that wins at once."""
    pb = V.passed(board)
    static = V.static_threats(pb)
    return static, bool(static) or engine_line_wins(engine, pb)


def defensive_base(p, engine):
    q = B.prepare(p)
    if not q:
        return None
    P = q["after"]
    if not V.usable(P):
        return None
    f = V.Facts(engine, P)
    if abs(f.best_cp) > CALM_CP or f.threat_cp < V.THREAT_CP or not calm(engine, P):
        return None
    threats, concrete = concrete_threat(engine, P)
    if not concrete:
        return None
    return q, f, threats


def met_real(p, engine):
    base = defensive_base(p, engine)
    if not base:
        return None
    q, f, threats = base
    loss = f.loss(q["m1"])
    if loss >= V.MET_LOSS_CP:
        return None
    return V.row("met", "met_real", q["after"], q["m1"], q, f, previous_fen=q["before"].fen(),
                 threat_basis="static" if threats else "engine_line", threat_cp=f.threat_cp, loss_cp=loss,
                 threat_moves=[m.uci() for m in threats])


def constructed_missed(p, engine, rng):
    base = defensive_base(p, engine)
    if not base:
        return None
    q, f, threats = base
    if not threats:
        return None
    P = q["after"]
    moves = [m for m in P.legal_moves if m != q["m1"]]
    rng.shuffle(moves)
    for m in moves[:8]:
        after = P.copy()
        after.push(m)
        if not any(V.wins(after, t) for t in threats):
            continue
        loss = f.loss(m)
        if loss >= V.MISS_LOSS_CP:
            return V.row("missed", "constructed_missed", P, m, q, f, previous_fen=q["before"].fen(), threat_basis="static",
                         threat_cp=f.threat_cp, loss_cp=loss, threat_moves=[t.uci() for t in threats])
    return None


def missed_real(p, engine):
    q = B.prepare(p)
    if not q:
        return None
    F, a, b, after = q["before"], q["m0"], q["m1"], q["after"]
    if not V.usable(F):
        return None
    pb = V.passed(F)
    if not (V.wins(pb, b) and V.wins(after, b)):
        return None
    f = V.Facts(engine, F)
    if abs(f.best_cp) > CALM_CP or not calm(engine, F):
        return None
    loss = f.loss(a)
    e = chess.Move.from_uci(f.best.pv[0])
    if loss < V.MISS_LOSS_CP or e == a:
        return None
    after_e = F.copy()
    after_e.push(e)
    if V.wins(after_e, b):
        return None
    return V.row("missed", "missed_real", F, a, q, f, threat_move=b.uci(), threat_basis="static", engine_after_cp=f.best_cp - loss,
                 loss_cp=loss, engine_best_move=e.uci())


def constructed_quiet(p, engine):
    q = B.prepare(p)
    if not q:
        return None
    F = q["before"]
    if not V.usable(F) or V.static_threats(V.passed(F)) or B.best_capture_net(V.passed(F)) >= 1:
        return None
    f = V.Facts(engine, F)
    if abs(f.best_cp) > CALM_CP or f.threat_cp >= V.NO_THREAT_CP or not calm(engine, F):
        return None
    e = chess.Move.from_uci(f.best.pv[0])
    return V.row("not_applicable", "constructed_quiet", F, e, q, f, threat_cp=f.threat_cp, loss_cp=0)


def blunder_without_threat(p, engine, want_hang):
    q = B.prepare(p)
    if not q:
        return None
    F, a, after = q["before"], q["m0"], q["after"]
    if not V.usable(F) or V.static_threats(V.passed(F)) or B.best_capture_net(V.passed(F)) >= 1:
        return None
    if (B.best_capture_net(after) >= V.MIN_GAIN) != want_hang:
        return None
    f = V.Facts(engine, F)
    if abs(f.best_cp) > CALM_CP or f.threat_cp >= V.NO_THREAT_CP or not calm(engine, F):
        return None
    loss = f.loss(a)
    if loss < V.MISS_LOSS_CP:
        return None
    return V.row("not_applicable", "hung_not_threat" if want_hang else "quiet_blunder", F, a, q, f, threat_cp=f.threat_cp,
                 loss_cp=loss)


def main():
    if (OUT / "FROZEN.md").exists():
        sys.exit("missed_threat_v2 is frozen (see FROZEN.md). Build a new version instead of overwriting it.")
    used = {json.loads(line)["puzzle_id"] for line in V1_SET.read_text().splitlines() if line.strip()}
    rng = random.Random(SEED)
    sample, defensive = V.load_pools()
    sample = [p for p in sample if p["id"] not in used]
    defensive = [p for p in defensive if p["id"] not in used]
    for p in sample + defensive:
        p["mate_theme"] = any(t.startswith("mate") or t.endswith("Mate") for t in p["themes"])
    print("pools:", len(sample), "general,", len(defensive), "defensive", flush=True)
    taken, shortfall, stats, items = set(), {}, {}, []
    with B.Engine() as engine:
        engine_name = engine.name
        steps = [
            (defensive, lambda p: met_real(p, engine), "met_real"),
            (defensive, lambda p: constructed_missed(p, engine, rng), "constructed_missed"),
            (sample, lambda p: missed_real(p, engine), "missed_real"),
            (sample, lambda p: constructed_quiet(p, engine), "constructed_quiet"),
            (sample, lambda p: blunder_without_threat(p, engine, True), "hung_not_threat"),
            (sample, lambda p: blunder_without_threat(p, engine, False), "quiet_blunder"),
        ]
        for pool, test, key in steps:
            got = V.fill(pool, test, key, taken, rng, shortfall, stats)
            items += got
            print(key, len(got), flush=True)
        adv, rejected = V.adversarial(engine)
    items += adv
    items.sort(key=lambda r: (r["category"], r["puzzle_id"]))
    random.Random(SEED + 2).shuffle(items)
    for i, r in enumerate(items, 1):
        r["id"] = f"mt2-{i:03d}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "positions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in items))
    counts = {}
    for r in items:
        counts[f"{r['category']}:{r['label']}"] = counts.get(f"{r['category']}:{r['label']}", 0) + 1
    prov = {"set": "missed_threat_v2", "rule": "LABEL_RULE.md", "seed": SEED, "engine": engine_name, "oracle_depth": V.ORACLE.depth,
            "calm_cp": CALM_CP, "calm_depth18_cp": CALM18_CP, "line_plies": LINE_PLIES, "miss_loss_cp": V.MISS_LOSS_CP,
            "met_loss_cp": V.MET_LOSS_CP, "threat_cp": V.THREAT_CP, "no_threat_cp": V.NO_THREAT_CP,
            "min_ply": V.MIN_PLY, "puzzle_file_sha256": B.sha256(B.PUZZLES),
            "excluded_v1_puzzles": len(used), "counts": counts, "pool": {"general_sample": len(sample), "defensive": len(defensive)},
            "shortfall": shortfall, "adversarial_rejected": rejected, "items": len(items), "detectors_run": False, "frozen": True}
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    print(json.dumps(counts, indent=1))
    print("shortfall:", shortfall, "| rejected adversarial:", len(rejected), "| items:", len(items))
    for r in rejected:
        print("REJECTED", r)


if __name__ == "__main__":
    main()
