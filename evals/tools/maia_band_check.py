"""Maia-3 band check (ADR 0012): does the Elo setting change how Maia-3 plays, down to the lowest ratings?

Positions come from real Lichess rapid games in which both players are rated 900 or lower (the git-ignored sample
`data/lichess/rapid_500_1800_2026-09.pgn`, plies 12 to 50, a fixed seed). For each position and each Elo setting, Maia-3 plays one
sampled move (temperature 1.0, as in a game) and one top move (temperature 0). Stockfish at depth 10 scores the sampled move for the
side to move, and also scores the move the real player made, which gives the comparison: how often real players rated 900 or lower
lose 200 centipawns or more in the same positions. The script imports only the Maia adapter, no detectors.

Each board is rebuilt from the game's start by replaying every earlier move, so Maia-3 gets the same move history it gets in a live
game (`--use-uci-history`, ADR 0012 decision 4). Scores are kept on one scale where a mate is always worth more than any
centipawn score: centipawns are clamped to +/-900 and a mate is +/-1000, so giving up a forced mate for a large lead counts as a
small loss, never as zero, and moving from a large lead into a mate is never an error.

The two measures are separate experiments: loss is measured on sampled moves (temperature 1.0), top-move match on top moves
(temperature 0). Intervals are 95% bootstrap intervals over positions (the same positions for every setting, so differences between
settings are paired). One sampled move per position and one seed: the intervals do not cover that sampling.

It measures one thing: whether a lower setting plays weaker. It does not show that Maia-3 plays like a player of that rating, and
it makes no Elo claim. The positions come from players rated 900 or lower, so the top of the range is not tested well.

Run from backend/ (needs Stockfish, Maia-3 and the sample):
  MAIA3_CMD=maia3-uci PYTHONPATH=. uv run python ../evals/tools/maia_band_check.py ../evals/reports/maia_band_check.json 300 [SAMPLE.pgn]
The sample defaults to data/lichess/rapid_500_1800_2026-09.pgn under the repo; pass a path when running from a git worktree, where the
git-ignored data/ folder is not present.
"""

from __future__ import annotations

import collections
import json
import os
import random
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import chess
import chess.engine
import chess.pgn

from app.engine import maia

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "data" / "lichess" / "rapid_500_1800_2026-09.pgn"
ELOS = [500, 700, 900, 1200, 1600, 2000]  # the settings tried; the accepted range is maia.MIN_ELO..MAX_ELO
MAX_RATING = 900
PLY_RANGE = (12, 50)
SEED = 7
BIG_LOSS = 200
BOOTSTRAPS = 2000
CP_CLAMP, MATE = 900, 1000


class Position(NamedTuple):
    start_fen: str
    history: list[str]  # the moves played before this position, in UCI
    real_move: str  # what the real player played here, in UCI
    rating: int  # the real player's Lichess rating


def to_score(score: chess.engine.Score) -> int:
    """One scale for a Stockfish score seen from one side: centipawns clamped to +/-CP_CLAMP, a mate is +/-MATE, so a mate always
    outranks any lead."""
    if score.is_mate():
        # The sign comes from the score, not from `mate()`: a mate just delivered (MateGiven) and a side that is checkmated (Mate(0))
        # both report 0 moves, but one is a win and the other a loss.
        return MATE if score.score(mate_score=MATE) > 0 else -MATE
    return max(-CP_CLAMP, min(CP_CLAMP, score.score()))


def positions(n: int, sample: Path | None = None) -> list[Position]:
    """Positions from games with both players rated MAX_RATING or lower, in a fixed random order."""
    found = []
    with (sample or SAMPLE).open() as f:
        while (g := chess.pgn.read_game(f)) is not None:
            try:
                w, b = int(g.headers["WhiteElo"]), int(g.headers["BlackElo"])
            except (KeyError, ValueError):
                continue
            if max(w, b) > MAX_RATING:
                continue
            board = g.board()
            start, played = board.fen(), []
            for ply, node in enumerate(g.mainline()):
                if PLY_RANGE[0] <= ply <= PLY_RANGE[1] and not board.is_game_over():
                    found.append(Position(start, list(played), node.move.uci(), w if board.turn else b))
                board.push(node.move)
                played.append(node.move.uci())
    random.Random(SEED).shuffle(found)
    return found[:n]


def bootstrap(rng: random.Random, values: list[float], other: list[float] | None = None) -> list[float]:
    """Means of resampled positions (paired with `other` when given: the mean difference values - other)."""
    n = len(values)
    out = []
    for _ in range(BOOTSTRAPS):
        idx = [rng.randrange(n) for _ in range(n)]
        out.append(sum(values[i] - (other[i] if other else 0) for i in idx) / n)
    return out


def interval(draws: list[float], digits: int = 3) -> list[float]:
    s = sorted(draws)
    return [round(s[int(0.025 * len(s))], digits), round(s[int(0.975 * len(s)) - 1], digits)]


def commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(out: str, n: int, sample: Path | None = None) -> None:
    sf = chess.engine.SimpleEngine.popen_uci(os.environ.get("STOCKFISH_PATH", "stockfish"))

    def score(board: chess.Board, color: chess.Color) -> int:
        return to_score(sf.analyse(board, chess.engine.Limit(depth=10))["score"].pov(color))

    base = maia.settings()
    sampled, top = dict(base, temperature=1.0), dict(base, temperature=0.0)
    losses: dict[object, list[int]] = {e: [] for e in ELOS} | {"real": []}
    agree: dict[int, list[int]] = {e: [] for e in ELOS}
    own_agree: list[int] = []
    pos = positions(n, sample)
    started = time.time()
    with maia.MaiaOpponent(sampled) as m1, maia.MaiaOpponent(top) as m0:
        for i, p in enumerate(pos):
            board = chess.Board(p.start_fen)
            for uci in p.history:
                board.push_uci(uci)  # the full move stack goes to Maia-3, as in a live game
            color = board.turn
            before = score(board, color)
            real = board.copy()
            real.push_uci(p.real_move)
            losses["real"].append(max(0, before - score(real, color)))
            for e in ELOS:
                after = board.copy()
                after.push_uci(m1.play(board, e))
                losses[e].append(max(0, before - score(after, color)))
                agree[e].append(int(m0.play(board, e) == p.real_move))
            own = min(maia.MAX_ELO, max(maia.MIN_ELO, round(p.rating / 100) * 100))
            own_agree.append(int(m0.play(board, own) == p.real_move))
            if (i + 1) % 50 == 0:
                print(i + 1, round(time.time() - started), "s", flush=True)
    sf.quit()

    rng = random.Random(SEED)
    big = {k: [int(x >= BIG_LOSS) for x in v] for k, v in losses.items()}
    count = len(pos)

    def row(key) -> dict:
        r = {"positions": count, "mean_cp_loss": round(sum(losses[key]) / count, 1),
             "mean_cp_loss_ci95": interval(bootstrap(rng, losses[key]), 1),
             "share_losing_200cp_or_more": round(sum(big[key]) / count, 3),
             "share_losing_200cp_or_more_ci95": interval(bootstrap(rng, big[key]))}
        if key != "real":
            r["top1_match_with_real_move"] = round(sum(agree[key]) / count, 3)
            r["top1_match_ci95"] = interval(bootstrap(rng, agree[key]))
        return r

    report = {str(e): row(e) for e in ELOS}
    report["real_players_rated_900_or_lower"] = row("real")  # the move they actually made, scored the same way
    report["share_losing_200cp_or_more_difference_from_previous_setting"] = {
        f"{ELOS[i]}_minus_{ELOS[i - 1]}": {"difference": round(sum(big[ELOS[i]]) / count - sum(big[ELOS[i - 1]]) / count, 3),
                                           "ci95_paired": interval(bootstrap(rng, big[ELOS[i]], big[ELOS[i - 1]]))}
        for i in range(1, len(ELOS))}
    report["conditioned_on_player_own_rating_top1_match"] = round(sum(own_agree) / count, 3)
    # What was actually run: the sampled process (temperature 1.0) and the top-move process (temperature 0), as each captured it.
    report["setup"] = {"sampled": m1.setup, "top_move": m0.setup}
    buckets = collections.Counter(p.rating // 100 * 100 for p in pos)
    report["sample"] = {"file": (sample or SAMPLE).name, "max_rating_of_either_player": MAX_RATING, "plies": list(PLY_RANGE),
                        "seed": SEED, "stockfish_depth": 10, "bootstrap_resamples": BOOTSTRAPS,
                        "rating_of_the_player_to_move": dict(sorted(buckets.items())),
                        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "tool_commit": commit()}
    Path(out).write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
