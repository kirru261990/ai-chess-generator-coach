"""Loss map (ADR 0019 amendment): each synced game sorted into ahead / level / behind after Black's 5th move, with its result.

The sort is taken from the depth-10 pass over the player's own games (`data/analysis/`), so it is a quick check, not a verdict (rule 5:
a game with no usable score at the checkpoint is left out and counted, never sorted as level). Everything here is a rate with its
denominator (rule 3); a zone with fewer than MIN_GAMES games carries `enough: false` so the screen shows no rate for it. Read-only,
imports no LLM code, records the engine and depth each game was sorted with in `searches` (rule 6), and changing ZONE_PLY, ZONE_CP or the result groups is a new VERSION (rule 6).
"""

from __future__ import annotations

import json
from pathlib import Path

from app import config

VERSION = "1"
ZONE_PLY = 10  # the position after Black's 5th move
ZONE_CP = 50  # ±0.5 pawns (owner, 2026-11-08)
MATE_CP = 10_000
MIN_GAMES = 10  # fewer games in a zone and no rate is read from it
ZONES = ("ahead", "level", "behind")
WIN = {"win"}
LOSS = {"checkmated", "resigned", "timeout", "abandoned"}
DRAW = {"stalemate", "agreed", "insufficient", "repetition", "50move", "timevsinsufficient"}


def outcome(result: str) -> str | None:
    """win, draw or loss for the player, or None for a result this version does not know."""
    if result in WIN:
        return "win"
    if result in LOSS:
        return "loss"
    if result in DRAW:
        return "draw"
    return None


def zone_of(cp: int | None, mate: int | None, color: str) -> str | None:
    """The zone for the player from White's-side score. None when there is no usable score (also a mate of 0, whose side is unknown)."""
    if mate is not None:
        if mate == 0:
            return None
        cp = MATE_CP if mate > 0 else -MATE_CP
    if cp is None:
        return None
    mine = cp if color == "white" else -cp
    if mine >= ZONE_CP:
        return "ahead"
    if mine <= -ZONE_CP:
        return "behind"
    return "level"


def compute(games: list[dict], analyses: list[dict]) -> dict:
    by_id = {a["source_id"]: a for a in analyses}
    left_out = {"not_analysed": 0, "too_short": 0, "no_score": 0, "unknown_result": 0}
    searches: dict[tuple[str, int | None], int] = {}
    zones = {z: {"zone": z, "games": 0, "wins": 0, "draws": 0, "losses": 0} for z in ZONES}
    for g in games:
        a = by_id.get(g["source_id"])
        if a is None:
            left_out["not_analysed"] += 1
            continue
        if len(a["positions"]) <= ZONE_PLY:
            left_out["too_short"] += 1
            continue
        res = outcome(g["user_result"])
        if res is None:
            left_out["unknown_result"] += 1
            continue
        p = a["positions"][ZONE_PLY]
        z = zone_of(p.get("cp"), p.get("mate"), g["user_color"])
        if z is None:
            left_out["no_score"] += 1
            continue
        key = (a.get("engine") or "unknown", (a.get("budget") or {}).get("depth"))
        searches[key] = searches.get(key, 0) + 1
        row = zones[z]
        row["games"] += 1
        row[{"win": "wins", "draw": "draws", "loss": "losses"}[res]] += 1
    losses = sum(r["losses"] for r in zones.values())
    sorted_games = sum(r["games"] for r in zones.values())
    for r in zones.values():
        r["loss_share"] = {"n": r["losses"], "of": losses}
        r["enough"] = r["games"] >= MIN_GAMES
    return {
        "version": VERSION,
        "zone_ply": ZONE_PLY,
        "threshold_cp": ZONE_CP,
        "min_games": MIN_GAMES,
        "searches": [
            {"engine": e, "depth": d, "games": n}
            for (e, d), n in sorted(searches.items(), key=lambda kv: str(kv[0]))
        ],
        "games_total": len(games),
        "sorted": sorted_games,
        "losses": losses,
        "left_out": left_out,
        "zones": list(zones.values()),
    }


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def own() -> dict:
    """The loss map over the player's synced games (empty when no Chess.com username is set)."""
    user = config.chesscom_username()
    if not user:
        return compute([], [])
    name = f"chesscom_{user.lower()}.jsonl"
    games = _read(config.DATA_DIR / "games" / name)
    analyses = _read(config.DATA_DIR / "analysis" / name)
    return compute(games, analyses)
