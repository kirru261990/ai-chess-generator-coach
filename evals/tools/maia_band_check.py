"""Maia-3 band check (ADR 0012): does the Elo setting change how Maia-3 plays, down to the lowest ratings?

Positions come from real Lichess rapid games in which both players are rated 900 or lower (the git-ignored sample
`data/lichess/rapid_500_1800_2026-09.pgn`, plies 12 to 50, a fixed seed). For each position and each Elo setting, Maia-3 plays one
sampled move (as in a game) and a top move (temperature 0). Stockfish at depth 10 scores the sampled move for the side to move.
The script imports only the Maia adapter, no detectors.

Each board is rebuilt from the game's start by replaying every earlier move, so Maia-3 gets the same move history it gets in a live
game (`--use-uci-history`, ADR 0012 decision 4). Scores are kept on one scale where a mate is always worth more than any
centipawn score: centipawns are clamped to +/-900 and a mate is +/-1000, so giving up a forced mate for a large lead counts as a
small loss, never as zero, and moving from a large lead into a mate is never an error.

It measures one thing: whether a lower setting plays weaker. It does not show that Maia-3 plays like a player of that rating, and
it makes no Elo claim. The positions come from players rated 900 or lower, so the top of the range is not tested well.

Run from backend/ (needs Stockfish, Maia-3 and the sample):
  MAIA3_CMD=maia3-uci PYTHONPATH=. uv run python ../evals/tools/maia_band_check.py ../evals/reports/maia_band_check.json 300 [SAMPLE.pgn]
The sample defaults to data/lichess/rapid_500_1800_2026-09.pgn under the repo; pass a path when running from a git worktree, where the
git-ignored data/ folder is not present.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

import chess
import chess.engine
import chess.pgn

from app.engine import maia

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "data" / "lichess" / "rapid_500_1800_2026-09.pgn"
ELOS = [500, 700, 900, 1200, 1600, 2000]
MAX_RATING = 900
PLY_RANGE = (12, 50)
SEED = 7


CP_CLAMP, MATE = 900, 1000


def to_score(score: chess.engine.Score) -> int:
    """One scale for a Stockfish score seen from one side: centipawns clamped to +/-CP_CLAMP, a mate is +/-MATE, so a mate always
    outranks any lead."""
    if score.is_mate():
        # The sign comes from the score, not from `mate()`: a mate just delivered (MateGiven) and a side that is checkmated (Mate(0))
        # both report 0 moves, but one is a win and the other a loss.
        return MATE if score.score(mate_score=MATE) > 0 else -MATE
    return max(-CP_CLAMP, min(CP_CLAMP, score.score()))


def positions(n: int, sample: Path | None = None) -> list[tuple[str, list[str], str, int]]:
    """(start FEN, the moves before this position in UCI, the real next move in UCI, the real player's rating) from games with both
    players rated MAX_RATING or lower."""
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
                    found.append((start, list(played), node.move.uci(), w if board.turn else b))
                board.push(node.move)
                played.append(node.move.uci())
    random.Random(SEED).shuffle(found)
    return found[:n]


def main(out: str, n: int, sample: Path | None = None) -> None:
    sf = chess.engine.SimpleEngine.popen_uci(os.environ.get("STOCKFISH_PATH", "stockfish"))

    def score(board: chess.Board, color: chess.Color) -> int:
        return to_score(sf.analyse(board, chess.engine.Limit(depth=10))["score"].pov(color))

    base = maia.settings()
    sampled, top = dict(base, temperature=1.0), dict(base, temperature=0.0)
    res = {e: {"loss": [], "big": 0, "agree": 0} for e in ELOS}
    own = 0
    pos = positions(n, sample)
    started = time.time()
    with maia.MaiaOpponent(sampled) as m1, maia.MaiaOpponent(top) as m0:
        for i, (start, history, real, rating) in enumerate(pos):
            board = chess.Board(start)
            for uci in history:
                board.push_uci(uci)  # the full move stack goes to Maia-3, as in a live game
            color = board.turn
            before = score(board, color)
            for e in ELOS:
                after = board.copy()
                after.push_uci(m1.play(board, e))
                loss = max(0, before - score(after, color))
                res[e]["loss"].append(loss)
                res[e]["big"] += loss >= 200
                res[e]["agree"] += m0.play(board, e) == real
            own += m0.play(board, min(2000, max(500, round(rating / 100) * 100))) == real
            if (i + 1) % 50 == 0:
                print(i + 1, round(time.time() - started), "s", flush=True)
    sf.quit()
    report = {str(e): {"positions": len(r["loss"]), "mean_cp_loss": round(sum(r["loss"]) / len(r["loss"]), 1),
                       "share_losing_200cp_or_more": round(r["big"] / len(r["loss"]), 3),
                       "top1_match_with_real_move": round(r["agree"] / len(r["loss"]), 3)} for e, r in res.items()}
    report["conditioned_on_player_own_rating_top1_match"] = round(own / len(pos), 3)
    # What was actually run: the sampled process (temperature 1.0) and the top-move process (temperature 0), as each captured it.
    report["setup"] = {"sampled": m1.setup, "top_move": m0.setup}
    report["sample"] = {"file": (sample or SAMPLE).name, "max_rating_of_either_player": MAX_RATING, "plies": list(PLY_RANGE), "seed": SEED,
                        "stockfish_depth": 10}
    Path(out).write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
