"""Build evals/sets/e2_v1: ~50 positions, each with one move played, for the E2 explanation eval (spec section 07, T20).

Source: the Lichess puzzle database (CC0), ratings 400-1199, as for real_play_v1. A puzzle gives a position where the
side to move has a clear best move. Two kinds of item:
  good: the puzzle's solution is played (engine-confirmed within GOOD_LOSS_CP of the best move)
  bad:  a legal move that is NOT the solution and that the engine says loses MISTAKE_RANGE centipawns (no mate scores)
Every item is a position, a colour and a move. No coach, prompt or detector is involved in choosing it, and nothing from
the owner's own games is used.

Independence: this file imports nothing from app/detectors/ or app/coach/.

Run from the repo root:  cd backend && uv run python ../evals/tools/build_e2_set.py [--pilot]
--pilot builds a small throwaway set in evals/runs/ (git-ignored) with a different seed, used only to debug the runner;
the real set never contains a pilot puzzle. The real set is written once and refuses to overwrite an existing one.
"""

import csv
import hashlib
import io
import json
import random
import sys
from pathlib import Path

import chess
import zstandard

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.stockfish import Budget, Engine

PUZZLES = ROOT / "data" / "lichess" / "lichess_db_puzzle.csv.zst"
OUT = ROOT / "evals" / "sets" / "e2_v1"
PILOT_OUT = ROOT / "evals" / "runs" / "e2_pilot"
SEED, PILOT_SEED = 20261008, 7777
ORACLE = Budget(depth=14)
GOOD_LOSS_CP = 50
MISTAKE_RANGE = (150, 600)
MAX_TRIES = 8
THEME_GROUPS = {  # quotas per kind (good, bad); the rest are "other"
    "hangingPiece": (6, 6),
    "fork": (3, 3),
    "pin_skewer": (2, 2),
    "other": (14, 14),
}
EXCLUDE = {"sacrifice", "attraction", "deflection", "intermezzo", "quietMove", "clearance", "zugzwang",
           "mate", "mateIn1", "mateIn2", "mateIn3", "mateIn4", "mateIn5"}  # mate scores are not rankable as centipawns


def group_of(themes):
    if "hangingPiece" in themes:
        return "hangingPiece"
    if "fork" in themes:
        return "fork"
    if "pin" in themes or "skewer" in themes:
        return "pin_skewer"
    return "other"


def reservoir(rng, per_group=300):
    """Seeded reservoir sample of usable puzzles per theme group, streaming the file once."""
    pools = {g: [] for g in THEME_GROUPS}
    seen = dict.fromkeys(THEME_GROUPS, 0)
    with PUZZLES.open("rb") as f, zstandard.ZstdDecompressor().stream_reader(f) as r:
        for row in csv.DictReader(io.TextIOWrapper(r, encoding="utf-8")):
            rating = int(row["Rating"])
            themes = row["Themes"].split()
            moves = row["Moves"].split()
            if not 400 <= rating <= 1199 or len(moves) < 2 or EXCLUDE & set(themes):
                continue
            g = group_of(themes)
            seen[g] += 1
            p = {"id": row["PuzzleId"], "fen": row["FEN"], "moves": moves, "rating": rating, "themes": themes}
            if len(pools[g]) < per_group:
                pools[g].append(p)
            else:
                j = rng.randrange(seen[g])
                if j < per_group:
                    pools[g][j] = p
    return pools, seen


def loss(engine, board, move):
    mover = board.turn
    best = engine.analyse(board, ORACLE, perspective=mover)
    after = board.copy()
    after.push(move)
    a = engine.analyse(after, ORACLE, perspective=mover)
    if best.score.mate is not None or a.score.mate is not None:
        return None  # mates are not given as centipawns
    return best.score.cp - a.score.cp


def position_of(p):
    board = chess.Board(p["fen"])
    try:
        board.push(chess.Move.from_uci(p["moves"][0]))  # the opponent's move that creates the puzzle
        solution = chess.Move.from_uci(p["moves"][1])
    except ValueError:
        return None
    return (board, solution) if solution in board.legal_moves else None


def make_item(kind, p, board, move, loss_cp):
    return {"kind": kind, "fen": board.fen(), "user_color": "white" if board.turn == chess.WHITE else "black",
            "move_uci": move.uci(), "move_san": board.san(move), "engine_loss_cp": loss_cp, "puzzle_id": p["id"],
            "rating": p["rating"], "themes": p["themes"], "group": group_of(p["themes"]),
            "source_url": f"https://lichess.org/training/{p['id']}"}


def build(rng, engine, quotas, exclude_ids=frozenset()):
    pools, seen = reservoir(rng)
    items, used = [], set(exclude_ids)
    for group, (n_good, n_bad) in quotas.items():
        pool = [p for p in pools[group] if p["id"] not in used]
        rng.shuffle(pool)
        want = {"good": n_good, "bad": n_bad}
        for p in pool:
            if not any(want.values()):
                break
            prepared = position_of(p)
            if prepared is None:
                continue
            board, solution = prepared
            kinds = [k for k in ("good", "bad") if want[k]]
            kind = rng.choice(kinds)
            if kind == "good":
                lost = loss(engine, board, solution)
                if lost is None or lost > GOOD_LOSS_CP:
                    continue
                move = solution
            else:
                move, lost = None, None
                legal = [m for m in board.legal_moves if m != solution]
                rng.shuffle(legal)
                for m in legal[:MAX_TRIES]:
                    cand = loss(engine, board, m)
                    if cand is not None and MISTAKE_RANGE[0] <= cand <= MISTAKE_RANGE[1]:
                        move, lost = m, cand
                        break
                if move is None:
                    continue
            items.append(make_item(kind, p, board, move, lost))
            used.add(p["id"])
            want[kind] -= 1
    rng.shuffle(items)
    for i, it in enumerate(items, 1):
        it["id"] = f"e2-{i:03d}"
    return items, seen


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv):
    pilot = "--pilot" in argv
    out = PILOT_OUT if pilot else OUT
    quotas = {"hangingPiece": (1, 1), "fork": (1, 0), "other": (1, 1)} if pilot else THEME_GROUPS
    if not pilot and (out / "positions.jsonl").exists():
        sys.exit(f"{out} already exists: a frozen set is never overwritten")
    rng = random.Random(PILOT_SEED if pilot else SEED)
    exclude = frozenset()
    if not pilot:
        pilot_file = PILOT_OUT / "positions.jsonl"
        if pilot_file.exists():
            exclude = frozenset(json.loads(line)["puzzle_id"] for line in pilot_file.read_text().splitlines() if line)
    with Engine() as engine:
        items, seen = build(rng, engine, quotas, exclude)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "positions.jsonl"
    path.write_text("".join(json.dumps(it) + "\n" for it in items))
    prov = {"seed": PILOT_SEED if pilot else SEED, "source": "Lichess puzzle database (CC0), ratings 400-1199",
            "puzzle_file_sha256": sha256(PUZZLES), "oracle": f"Stockfish depth {ORACLE.depth}",
            "good_within_cp": GOOD_LOSS_CP, "mistake_range_cp": list(MISTAKE_RANGE), "quotas": quotas,
            "excluded_puzzles": len(exclude), "usable_puzzles_seen_per_group": seen, "items": len(items)}
    (out / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    kinds = {k: sum(i["kind"] == k for i in items) for k in ("good", "bad")}
    print(f"wrote {len(items)} items to {path}: {kinds}")


if __name__ == "__main__":
    main(sys.argv[1:])
