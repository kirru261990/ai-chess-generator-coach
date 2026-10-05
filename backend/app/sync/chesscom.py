"""Chess.com public-API sync (T08).

No credentials. Requests are made strictly one at a time and carry a User-Agent
with contact info, as Chess.com asks. Imported text (PGN, usernames) is data,
never instructions.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from app import config

API = "https://api.chess.com/pub"


class SyncError(Exception):
    """Raised with a stable error code in `code`."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SyncedGame:
    source: str  # "chesscom"
    source_id: str  # the game URL; the dedupe key
    user_color: str  # "white" | "black"
    opponent: str
    user_rating: int | None
    opponent_rating: int | None
    user_result: str  # Chess.com result code for the user: win, checkmated, resigned, ...
    time_control: str  # e.g. "600" or "900+10"
    end_time: int  # unix seconds
    pgn: str


def make_client(user_agent: str | None = None, transport: httpx.BaseTransport | None = None):
    ua = user_agent or config.chesscom_user_agent()
    if not ua:
        raise SyncError("missing_user_agent", "set CHESSCOM_USER_AGENT with contact info")
    return httpx.Client(headers={"User-Agent": ua}, timeout=30, transport=transport)


def _get_json(client: httpx.Client, url: str) -> dict:
    for attempt in range(3):
        r = client.get(url)
        if r.status_code == 429 and attempt < 2:  # polite back-off, then retry
            time.sleep(float(r.headers.get("Retry-After", 2)))
            continue
        break
    if r.status_code == 404:
        raise SyncError("player_not_found", f"not found: {url}")
    if r.status_code != 200:
        raise SyncError("upstream_error", f"{url} returned {r.status_code}")
    return r.json()


def list_archives(client: httpx.Client, username: str) -> list[str]:
    """Monthly archive URLs, oldest first."""
    return _get_json(client, f"{API}/player/{username.lower()}/games/archives")["archives"]


def parse_game(raw: dict, username: str) -> SyncedGame | None:
    """Normalise one Chess.com game; None if it lacks what we need or is not the user's."""
    white, black = raw.get("white", {}), raw.get("black", {})
    me = username.lower()
    if white.get("username", "").lower() == me:
        color, mine, theirs = "white", white, black
    elif black.get("username", "").lower() == me:
        color, mine, theirs = "black", black, white
    else:
        return None
    if not (raw.get("url") and raw.get("pgn") and raw.get("time_control")):
        return None
    return SyncedGame(
        source="chesscom",
        source_id=raw["url"],
        user_color=color,
        opponent=theirs.get("username", ""),
        user_rating=mine.get("rating"),
        opponent_rating=theirs.get("rating"),
        user_result=mine.get("result", ""),
        time_control=raw["time_control"],
        end_time=raw.get("end_time", 0),
        pgn=raw["pgn"],
    )


def is_case_study_game(raw: dict, allowed: frozenset[str]) -> bool:
    """Standard-chess rapid games at the fixed case-study time controls (10|0, 15|10)."""
    return (
        raw.get("rules") == "chess"
        and raw.get("time_class") == "rapid"
        and raw.get("time_control") in allowed
        and raw.get("rated", True)
    )


def fetch_games(
    client: httpx.Client,
    username: str,
    allowed: frozenset[str] | None = None,
    max_games: int | None = None,
) -> list[SyncedGame]:
    """Fetch case-study games, newest month first, one request at a time."""
    allowed = allowed if allowed is not None else config.case_study_time_controls()
    games: list[SyncedGame] = []
    for url in reversed(list_archives(client, username)):
        month = _get_json(client, url).get("games", [])
        for raw in sorted(month, key=lambda g: g.get("end_time", 0), reverse=True):
            if is_case_study_game(raw, allowed) and (g := parse_game(raw, username)):
                games.append(g)
        if max_games is not None and len(games) >= max_games:
            return games[:max_games]
    return games


class GameStore:
    """JSON-lines store under data/ (git-ignored), deduplicated by source_id."""

    def __init__(self, path: Path):
        self.path = path

    def _load_ids(self) -> set[str]:
        if not self.path.exists():
            return set()
        with self.path.open() as f:
            return {json.loads(line)["source_id"] for line in f if line.strip()}

    def add_new(self, games: list[SyncedGame]) -> int:
        """Append games not already stored; return how many were new."""
        seen = self._load_ids()
        fresh = []
        for g in games:
            if g.source_id not in seen:
                seen.add(g.source_id)
                fresh.append(g)
        if fresh:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                for g in fresh:
                    f.write(json.dumps(asdict(g)) + "\n")
        return len(fresh)

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open() as f:
            return [json.loads(line) for line in f if line.strip()]


def sync_chesscom(
    username: str | None = None,
    max_games: int | None = None,
    client: httpx.Client | None = None,
    store: GameStore | None = None,
) -> dict:
    username = username or config.chesscom_username()
    if not username:
        raise SyncError("missing_username", "set CHESSCOM_USERNAME or pass a username")
    store = store or GameStore(config.DATA_DIR / "games" / f"chesscom_{username.lower()}.jsonl")
    own = client is None
    client = client or make_client()
    try:
        games = fetch_games(client, username, max_games=max_games)
    finally:
        if own:
            client.close()
    new = store.add_new(games)
    return {"username": username, "fetched": len(games), "new": new, "total": len(store.all())}
