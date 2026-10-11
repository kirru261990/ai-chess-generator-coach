"""The practice bank (T25) and training sessions (T44, spec D3).

Two sources of positions, both with the player to move and a known good answer:

- `own`: positions from the player's own synced games where a detector (`hanging_own` v2 or `missed_free` v2) counted
  a miss. The answer is the engine's best move from the stored fast pass (depth 10).
- `lichess`: public Lichess puzzles (CC0) with the theme `hangingPiece` or similar, in a rating band. The CSV gives the
  position *before* the opponent's last move and the move list, so the position shown is the one after `Moves[0]`
  and the answer is `Moves[1]`. Only IDs, FENs and moves are stored, never the raw CSV.

Held-out rule (spec D3): a fixed 20% of puzzle IDs (by hash of the ID) are *never* served as practice, hint targets or
coaching context; they are used only as the single test position in a session. The split depends on the ID alone, so
it never changes between runs. The same rule holds out 1 in 5 own-game positions.

Motifs: `missed_free` sessions use the player's own misses plus Lichess puzzles whose answer wins a free piece (puzzles
whose answer is checkmate are left out: that is a different skill). Lichess has no equivalent puzzles for `hanging_own`
(leaving a piece where it can be taken), so those sessions use the player's own positions in every slot, from different
games.

Pure functions: no engine and no network. The caller supplies randomness (a seed) and the data.

  uv run python -m app.learner.bank build   # data/bank/bank_v1.json from data/lichess/ and data/analysis/
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

import chess

from app import config
from app.detectors import missed_free
from app.engine.batch import SCHEMA, game_id
from app.learner import patterns

BANK_VERSION = 1
HELD_OUT_SHARE = 5  # 1 in 5 puzzle IDs is held out
DEFAULT_THEMES = ("hangingPiece",)
RATING_RANGE = (400, 1100)  # Lichess puzzle rating; the player is 500-700 on Chess.com
PRACTICE_PER_POOL = 200
HELD_OUT_PER_POOL = 60
OWN_MOTIFS = ("hanging_own", "missed_free")
MOTIF_LABEL = {
    "hanging_own": "leaving a piece where it can be taken",
    "missed_free": "missing a free piece",
}


class BankError(Exception):
    pass


def is_held_out(puzzle_id: str) -> bool:
    """True for the fixed 20% of puzzle IDs kept for tests only. Depends on the ID alone."""
    return int(hashlib.sha256(puzzle_id.encode()).hexdigest(), 16) % HELD_OUT_SHARE == 0


def puzzle_item(row: dict) -> dict | None:
    """A bank item from one Lichess CSV row, or None if the row is unusable.

    The row's FEN is the position before the opponent's last move (`Moves[0]`); the item is the position after it.
    """
    moves = row["Moves"].split()
    if len(moves) < 2:
        return None
    try:
        board = chess.Board(row["FEN"])
        opp = chess.Move.from_uci(moves[0])
        if opp not in board.legal_moves:
            return None
        board.push(opp)
        answer = chess.Move.from_uci(moves[1])
        if answer not in board.legal_moves:
            return None
        rating = int(row["Rating"])
        wins_free = chess.square_name(answer.to_square) in {h.square for h in missed_free.free_pieces(board)}
        board.push(answer)
        mates = board.is_checkmate()
        board.pop()
        if not wins_free or mates:  # a puzzle for this bank wins a free piece and is not a mate
            return None
    except (ValueError, KeyError):
        return None
    pid = row["PuzzleId"]
    return {
        "id": f"lichess:{pid}",
        "source": "lichess",
        "fen": board.fen(),
        "opponent_move": opp.uci(),
        "answer": answer.uci(),
        "line": moves[1:],
        "motif": "missed_free",
        "rating": rating,
        "themes": row["Themes"].split(),
        "popularity": int(row.get("Popularity") or 0),
        "held_out": is_held_out(pid),
    }


def select_puzzles(
    rows,
    themes: tuple[str, ...] = DEFAULT_THEMES,
    rating_range: tuple[int, int] = RATING_RANGE,
    practice: int = PRACTICE_PER_POOL,
    held_out: int = HELD_OUT_PER_POOL,
) -> list[dict]:
    """The most popular matching puzzles, up to `practice` practice items and `held_out` held-out items.

    `rows` is any iterable of CSV row dicts. Ties are broken by ID, so the result is the same on every run.
    """
    wanted = set(themes)
    lo, hi = rating_range
    candidates = []
    for row in rows:
        if not wanted.intersection(row["Themes"].split()):
            continue
        try:
            if not lo <= int(row["Rating"]) <= hi:
                continue
        except (ValueError, KeyError):
            continue
        item = puzzle_item(row)
        if item is not None:
            candidates.append(item)
    candidates.sort(key=lambda i: (-i["popularity"], i["id"]))
    out, counts = [], {True: 0, False: 0}
    limits = {True: held_out, False: practice}
    for item in candidates:
        if counts[item["held_out"]] < limits[item["held_out"]]:
            counts[item["held_out"]] += 1
            out.append(item)
    return out


def own_miss_items(games: list[dict], analyses: dict[str, dict]) -> list[dict]:
    """Positions from the player's own games where a detector counted a miss, with the engine's best move as the answer.

    Only moves the detectors classify as `missed` (the engine confirmed a loss; uncertain ones are skipped). A position
    appears once. Games without a current-schema analysis are skipped.
    """
    items, seen = [], set()
    for game in games:
        analysis = analyses.get(game["source_id"])
        if analysis is None or analysis.get("schema") != SCHEMA:
            continue
        gid = game_id(game["source_id"])
        for ply, board, move, evidence in patterns.user_moves(analysis, game["user_color"]):
            best = analysis["positions"][ply].get("best")
            if best is None or best == move.uci():
                continue
            for motif, detector in patterns.DETECTORS.items():
                if detector.detect(board, move, evidence).outcome != "missed":
                    continue
                key = (board.fen(), motif)
                if key in seen:
                    continue
                seen.add(key)
                items.append({
                    "id": f"own:{gid}:{ply}:{motif}",
                    "source": "own",
                    "fen": board.fen(),
                    "answer": best,
                    "line": [best],
                    "played": move.uci(),
                    "motif": motif,
                    "game": gid,
                    "ply": ply,
                    "time_control": game.get("time_control"),
                    "held_out": is_held_out(f"own:{gid}:{ply}:{motif}"),
                })
    items.sort(key=lambda i: (i["game"], i["ply"], i["motif"]))
    return items


def build_bank(own: list[dict], puzzles: list[dict], snapshot: dict) -> dict:
    """The stored bank. `snapshot` says which dataset the puzzles came from (size and date, never a copy)."""
    return {
        "bank_version": BANK_VERSION,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rules": {
            "themes": list(DEFAULT_THEMES), "rating_range": list(RATING_RANGE),
            "held_out": f"1 in {HELD_OUT_SHARE} puzzle ids, by sha256 of the id",
            "own_motifs": list(OWN_MOTIFS),
        },
        "puzzle_snapshot": snapshot,
        "own": own,
        "puzzles": puzzles,
    }


def validate(bank: dict) -> None:
    """Fail closed on a bank that would break a rule: a held-out puzzle outside the hash rule, or a bad answer."""
    for item in bank["own"] + bank["puzzles"]:
        board = chess.Board(item["fen"])
        if chess.Move.from_uci(item["answer"]) not in board.legal_moves:
            raise BankError(f"{item['id']}: the answer is not legal")
        if item["source"] == "lichess" and item["held_out"] != is_held_out(item["id"].split(":", 1)[1]):
            raise BankError(f"{item['id']}: held-out flag disagrees with the hash rule")
        if item["source"] == "own" and item["held_out"] != is_held_out(item["id"]):
            raise BankError(f"{item['id']}: held-out flag disagrees with the hash rule")


# ---------------------------------------------------------------- sessions


def new_session(bank: dict, motif: str, seed: int, avoid: frozenset[str] = frozenset(), retest: tuple[dict, ...] = ()) -> list[dict]:
    """Five items, the held-out test always last.

    `missed_free`: two of the player's own misses, two practice puzzles, one held-out puzzle.
    `hanging_own`: four of the player's own misses (from different games where possible), one held-out own position.
    `avoid` holds item ids seen recently, so a session does not repeat them while others exist. `retest` holds items
    due again (first try wrong 7+ days ago); they take practice slots first. A bank too thin to fill the session raises
    BankError instead of silently making a shorter one.
    """
    if motif not in OWN_MOTIFS:
        raise BankError(f"unknown motif {motif!r}")
    rng = random.Random(seed)

    def pick(pool: list[dict], n: int, distinct_games: bool = False) -> list[dict]:
        fresh = [i for i in pool if i["id"] not in avoid]
        stale = [i for i in pool if i["id"] in avoid]
        rng.shuffle(fresh)
        rng.shuffle(stale)
        ordered, chosen, games = fresh + stale, [], set()
        for i in ordered:
            if len(chosen) == n:
                break
            if distinct_games and i.get("game") in games:
                continue
            chosen.append(i)
            games.add(i.get("game"))
        for i in ordered:  # too few distinct games: top up from any
            if len(chosen) == n:
                break
            if i not in chosen:
                chosen.append(i)
        return chosen

    own_pool = [i for i in bank["own"] if i["motif"] == motif]
    own_practice = [i for i in own_pool if not i["held_out"]]
    due = [i for i in retest if not i["held_out"] and i["motif"] == motif][:2]
    if motif == "missed_free":
        own = pick(own_practice, 2, distinct_games=True)
        curated = due + pick([i for i in bank["puzzles"] if not i["held_out"] and i not in due], 2 - len(due))
        test = pick([i for i in bank["puzzles"] if i["held_out"]], 1)
        plan = (("own", own), ("practice", curated), ("held_out", test))
    else:
        own = due + pick([i for i in own_practice if i not in due], 4 - len(due), distinct_games=True)
        test = pick([i for i in own_pool if i["held_out"]], 1)
        plan = (("own", own), ("held_out", test))
    sizes = {kind: (len(group), want) for (kind, group), want in zip(plan, (2, 2, 1) if motif == "missed_free" else (4, 1))}
    if any(have < want for have, want in sizes.values()):
        raise BankError(f"the bank is too small for a session on {motif}: {sizes}")
    items = []
    for kind, group in plan:
        for item in group:
            label = "retest" if item in due else kind
            items.append({**item, "kind": label})
    return items


def side_to_move(fen: str) -> str:
    return "white" if chess.Board(fen).turn == chess.WHITE else "black"


def public_item(index: int, item: dict) -> dict:
    """What the page may see before an attempt: the position and who moves, never the answer."""
    return {
        "index": index,
        "kind": item["kind"],
        "fen": item["fen"],
        "side": side_to_move(item["fen"]),
        "hints_allowed": item["kind"] != "held_out",
    }


def check_move(item: dict, uci: str, loss_cp: int | None = None, tolerance_cp: int = 30) -> dict:
    """Is `uci` accepted? The stored answer always is. Any other legal move is accepted only if the caller measured its
    engine loss (centipawns the mover gives up against the best move) and it is within `tolerance_cp` (spec D3: equivalent
    good moves are accepted). With no measurement, only the stored answer counts, which errs towards "not yet accepted".
    """
    board = chess.Board(item["fen"])
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        return {"legal": False, "correct": False, "accepted_by": None}
    if move not in board.legal_moves:
        return {"legal": False, "correct": False, "accepted_by": None}
    if uci == item["answer"]:
        return {"legal": True, "correct": True, "accepted_by": "answer"}
    if loss_cp is not None and loss_cp <= tolerance_cp:
        return {"legal": True, "correct": True, "accepted_by": "engine_equivalent", "loss_cp": loss_cp}
    return {"legal": True, "correct": False, "accepted_by": None, **({"loss_cp": loss_cp} if loss_cp is not None else {})}


# ---------------------------------------------------------------- build

def _puzzle_rows(path: Path):
    import zstandard

    with path.open("rb") as raw, zstandard.ZstdDecompressor().stream_reader(raw) as reader:
        yield from csv.DictReader(io.TextIOWrapper(reader, encoding="utf-8", newline=""))


def main(argv: list[str]) -> None:
    if argv != ["build"]:
        sys.exit(__doc__)
    username = config.chesscom_username()
    if not username:
        sys.exit("set CHESSCOM_USERNAME in .env")
    puzzle_path = config.DATA_DIR / "lichess" / "lichess_db_puzzle.csv.zst"
    games = [json.loads(line) for line in (config.DATA_DIR / "games" / f"chesscom_{username.lower()}.jsonl").read_text().splitlines() if line.strip()]
    analyses = patterns._load_analyses(config.DATA_DIR / "analysis" / f"chesscom_{username.lower()}.jsonl")
    own = own_miss_items(games, analyses)
    puzzles = select_puzzles(_puzzle_rows(puzzle_path))
    stat = puzzle_path.stat()
    snapshot = {"file": puzzle_path.name, "bytes": stat.st_size, "modified": datetime.fromtimestamp(stat.st_mtime, UTC).date().isoformat()}
    bank = build_bank(own, puzzles, snapshot)
    validate(bank)
    out = config.DATA_DIR / "bank" / "bank_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bank, indent=1) + "\n")
    held = sum(1 for p in puzzles if p["held_out"])
    by_motif = {m: sum(1 for i in own if i["motif"] == m) for m in OWN_MOTIFS}
    print(f"bank written to {out}\n  own positions: {len(own)} {by_motif}\n  puzzles: {len(puzzles)} ({held} held out)")


if __name__ == "__main__":
    main(sys.argv[1:])
