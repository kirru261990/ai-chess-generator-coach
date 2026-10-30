"""Stream a Lichess monthly games file and keep a small sample. Imports nothing from app/detectors/. Never downloads the whole file.

Run:  cd backend && uv run python ../evals/tools/lichess_stream_sample.py [--month 2026-09] [--games 3000] [--max-gb 3] [--out PATH]

Reads https://database.lichess.org/standard/lichess_db_standard_rated_<month>.pgn.zst (CC0) as a stream, decompresses it on the fly
and keeps rated Rapid games where both players are rated 600-1200, the game ended normally and has at least 20 moves. It stops at
`--games` kept games or `--max-gb` compressed bytes read, whichever comes first. The file is in time order, so the sample is the
start of the month (stated in the sidecar JSON). Output (raw games, git-ignored): data/lichess/rapid_600_1200_<month>.pgn
plus a .json sidecar with the counts and the byte position reached. ADR 0001 section 3; TASKS T13 and T14b.
"""

import argparse
import io
import json
import sys
import urllib.request
from pathlib import Path

import chess.pgn
import zstandard

ROOT = Path(__file__).resolve().parents[2]
LOW, HIGH = 600, 1200


class Counting(io.RawIOBase):
    """A readable wrapper that counts the compressed bytes taken from the network and stops at a cap."""

    def __init__(self, raw, cap):
        self.raw, self.cap, self.n = raw, cap, 0

    def readable(self):
        return True

    def readinto(self, b):
        if self.n >= self.cap:
            return 0
        chunk = self.raw.read(min(len(b), self.cap - self.n))
        b[: len(chunk)] = chunk
        self.n += len(chunk)
        return len(chunk)


def keep(game) -> bool:
    h = game.headers
    try:
        w, b = int(h.get("WhiteElo", "")), int(h.get("BlackElo", ""))
    except ValueError:
        return False
    if "Rapid" not in h.get("Event", "") or h.get("Termination") != "Normal":
        return False
    return LOW <= w <= HIGH and LOW <= b <= HIGH and sum(1 for _ in game.mainline_moves()) >= 20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="2026-09")
    ap.add_argument("--games", type=int, default=3000)
    ap.add_argument("--max-gb", type=float, default=3.0)
    ap.add_argument("--out")
    a = ap.parse_args()
    url = f"https://database.lichess.org/standard/lichess_db_standard_rated_{a.month}.pgn.zst"
    out = Path(a.out) if a.out else ROOT / "data" / "lichess" / f"rapid_{LOW}_{HIGH}_{a.month}.pgn"
    out.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ai-chess-coach-research (github.com/kirru261990/ai-chess-generator-coach)"})
    kept = seen = 0
    with urllib.request.urlopen(req) as resp:
        src = Counting(resp, int(a.max_gb * 1e9))
        text = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(io.BufferedReader(src)), encoding="utf-8", errors="replace")
        with out.open("w") as f:
            while kept < a.games:
                try:
                    g = chess.pgn.read_game(text)
                except Exception:  # noqa: BLE001 (a cut stream ends mid-game)
                    break
                if g is None:
                    break
                seen += 1
                if keep(g):
                    print(g, file=f, end="\n\n")
                    kept += 1
                if seen % 20000 == 0:
                    print(f"seen {seen}, kept {kept}, read {src.n / 1e9:.2f} GB", file=sys.stderr, flush=True)
    meta = {"source": url, "licence": "CC0", "kept": kept, "seen": seen, "compressed_bytes_read": src.n,
            "note": "start of the month only (the file is in time order); rated Rapid, both 600-1200, Termination Normal, >= 20 moves"}
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
