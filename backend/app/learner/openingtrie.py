"""What players in a rating band actually play in each repertoire opening (ADR 0022).

Counts the first moves of rated Rapid games from the public Lichess database (CC0) for five openings: Jobava London, Italian
and Queen's Gambit (White), Caro-Kann and King's Indian (Black). The games are read as a stream and only the counts of move
prefixes are kept, never the games. Imports no LLM or detector code. PGN text is data only.

Run (from backend/; reads part of https://database.lichess.org, about 300 MB, CC0):
  uv run python -m app.learner.openingtrie build [--month 2026-09] [--max-gb 0.3] [--low 700] [--high 1500]
  uv run python -m app.learner.openingtrie summary

Output (git-ignored): data/repertoire/openings_<month>_<low>_<high>.json
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from app import config

VERSION = "1"  # the opening gates and the saved layout; changing a gate is a new version (rule 6)
MIN_COUNT = 2  # a line seen once is noise and is not saved
MAX_PLIES = 20  # to Black's 10th move
MIN_PLIES = 12  # a game must reach at least this far to show the opening
DEFAULT_LOW, DEFAULT_HIGH = 700, 1500
_COMMENT = re.compile(r"\{[^}]*\}")
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9=+#\-]*")


def moves_of(movetext: str, max_plies: int | None = None) -> list[str]:
    """The SAN moves in a PGN move text, without comments, move numbers, marks or the result."""
    out: list[str] = []
    for tok in _TOKEN.findall(_COMMENT.sub(" ", movetext)):
        out.append(tok)
        if max_plies is not None and len(out) >= max_plies:
            break
    return out


@dataclass(frozen=True)
class Opening:
    key: str
    name: str
    side: str  # the side the player has
    gate: Callable[[list[str]], bool]

    def matches(self, moves: list[str]) -> bool:
        return self.gate(moves)


def _by(moves: list[str], white: bool, upto: int) -> set[str]:
    return set(moves[(0 if white else 1) : upto : 2])


def _jobava(m: list[str]) -> bool:
    return m[:1] == ["d4"] and {"Nc3", "Bf4"} <= _by(m, True, 8)


def _italian(m: list[str]) -> bool:
    return m[:5] == ["e4", "e5", "Nf3", "Nc6", "Bc4"]


def _queens_gambit(m: list[str]) -> bool:
    return m[:3] == ["d4", "d5", "c4"]


def _caro_kann(m: list[str]) -> bool:
    return m[:2] == ["e4", "c6"]


def _kings_indian(m: list[str]) -> bool:
    return m[:1] == ["d4"] and {"Nf6", "g6", "Bg7", "d6"} <= _by(m, False, 10)


OPENINGS: dict[str, Opening] = {
    o.key: o
    for o in (
        Opening("jobava", "Jobava London", "white", _jobava),
        Opening("italian", "Italian Game", "white", _italian),
        Opening("queens_gambit", "Queen's Gambit", "white", _queens_gambit),
        Opening("caro_kann", "Caro-Kann Defence", "black", _caro_kann),
        Opening("kings_indian", "King's Indian Defence", "black", _kings_indian),
    )
}


@dataclass
class Tally:
    games: int = 0
    nodes: Counter = field(
        default_factory=Counter
    )  # move prefix (tuple of SAN) -> games that played it


def iter_games(lines: Iterable[str]) -> Iterator[tuple[dict[str, str], str]]:
    """(headers, move text) for each game in a PGN stream. Only the headers the counter needs are kept."""
    headers: dict[str, str] = {}
    text: list[str] = []
    for line in lines:
        if line.startswith("[Event ") and (headers or text):
            yield headers, " ".join(text)
            headers, text = {}, []
        if line.startswith("["):
            m = re.match(r'\[(\w+) "(.*)"\]', line)
            if m and m.group(1) in ("Event", "WhiteElo", "BlackElo"):
                headers[m.group(1)] = m.group(2)
        elif line.strip():
            text.append(line.strip())
    if headers or text:
        yield headers, " ".join(text)


def _in_band(h: dict[str, str], low: int, high: int) -> bool:
    try:
        w, b = int(h.get("WhiteElo", "")), int(h.get("BlackElo", ""))
    except ValueError:
        return False  # an unreadable rating is not known to be in the band
    return "Rapid" in h.get("Event", "") and low <= w <= high and low <= b <= high


def count(
    lines: Iterable[str],
    low: int = DEFAULT_LOW,
    high: int = DEFAULT_HIGH,
    max_plies: int = MAX_PLIES,
    min_plies: int = 0,
) -> dict:
    """Tally the first moves of every game in the band, per opening. `_stats` counts games seen and skipped."""
    tallies = {k: Tally() for k in OPENINGS}
    seen = skipped = 0
    for headers, text in iter_games(lines):
        seen += 1
        if not _in_band(headers, low, high):
            skipped += 1
            continue
        moves = moves_of(text, max_plies)
        if len(moves) < min_plies:
            skipped += 1
            continue
        for key, opening in OPENINGS.items():
            if opening.matches(moves):
                t = tallies[key]
                t.games += 1
                for i in range(1, len(moves) + 1):
                    t.nodes[tuple(moves[:i])] += 1
    return {**tallies, "_stats": {"seen": seen, "skipped": skipped}}


def save(counts: dict, out_dir: Path, month: str, low: int, high: int, source: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    openings = {}
    for key, o in OPENINGS.items():
        t: Tally = counts[key]
        lines = [[" ".join(p), n] for p, n in t.nodes.items() if n >= MIN_COUNT]
        openings[key] = {"name": o.name, "side": o.side, "games": t.games, "lines": sorted(lines)}
    doc = {
        "version": VERSION,
        "month": month,
        "band": [low, high],
        "source": source,
        "licence": "CC0",
        "seen": counts["_stats"]["seen"],
        "skipped": counts["_stats"]["skipped"],
        "openings": openings,
    }
    path = out_dir / f"openings_{month}_{low}_{high}.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n")
    tmp.replace(path)
    return path


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def data_dir() -> Path:
    return config.DATA_DIR / "repertoire"


class _Capped(io.RawIOBase):
    """A readable wrapper that counts the compressed bytes taken from the network and stops at a cap."""

    def __init__(self, raw, cap: int):
        self.raw, self.cap, self.n = raw, cap, 0

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        if self.n >= self.cap:
            return 0
        chunk = self.raw.read(min(len(b), self.cap - self.n))
        b[: len(chunk)] = chunk
        self.n += len(chunk)
        return len(chunk)


def build(month: str, max_gb: float, low: int, high: int) -> Path:
    import zstandard

    url = f"https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-chess-coach-research (github.com/kirru261990/ai-chess-generator-coach)"
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        src = _Capped(resp, int(max_gb * 1e9))
        text = io.TextIOWrapper(
            zstandard.ZstdDecompressor().stream_reader(io.BufferedReader(src)),
            encoding="utf-8",
            errors="replace",
        )
        counts = count(_progress(text, src), low, high, MAX_PLIES, MIN_PLIES)
    how = "capped at" if src.n >= src.cap else "ended after"
    return save(
        counts,
        data_dir(),
        month,
        low,
        high,
        f"{url} ({how} {src.n / 1e9:.2f} GB; start of the month)",
    )


def _progress(lines: Iterable[str], src: _Capped) -> Iterator[str]:
    """Pass the lines on, print progress, and tell a planned stop at the cap (fine) from a stream fault before it (raised)."""
    n = 0
    try:
        for line in lines:
            if line.startswith("[Event "):
                n += 1
                if n % 50000 == 0:
                    print(f"{n} games, {src.n / 1e9:.2f} GB read", file=sys.stderr, flush=True)
            yield line
    except Exception as e:
        if src.n < src.cap:
            print(f"stream failed after {src.n / 1e9:.2f} GB: {type(e).__name__}", file=sys.stderr)
            raise


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--month", default="2026-09")
    b.add_argument("--max-gb", type=float, default=0.3)
    b.add_argument("--low", type=int, default=DEFAULT_LOW)
    b.add_argument("--high", type=int, default=DEFAULT_HIGH)
    sub.add_parser("summary")
    a = ap.parse_args()
    if a.cmd == "build":
        print(build(a.month, a.max_gb, a.low, a.high))
        return
    for path in sorted(data_dir().glob("openings_*.json")):
        d = load(path)
        print(path.name, f"seen {d['seen']}", {k: v["games"] for k, v in d["openings"].items()})


if __name__ == "__main__":
    main()
