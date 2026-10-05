"""Tools over synced (real) games: list them and review one (spec §06 review_game)."""

from app import config
from app.core.game import GameError
from app.engine.batch import BATCH_BUDGET, AnalysisStore, analyse_game, game_id
from app.engine.shared import get_engine
from app.learner.review import review_game
from app.sync.chesscom import GameStore


def _stores() -> tuple[GameStore, AnalysisStore]:
    username = config.chesscom_username()
    if not username:
        raise GameError("missing_username", "set CHESSCOM_USERNAME")
    name = f"chesscom_{username.lower()}.jsonl"
    return (
        GameStore(config.DATA_DIR / "games" / name),
        AnalysisStore(config.DATA_DIR / "analysis" / name),
    )


def list_synced_games(limit: int = 20) -> list[dict]:
    games, analyses = _stores()
    rows = sorted(games.all(), key=lambda g: g["end_time"], reverse=True)[:limit]
    return [
        {
            "game_id": game_id(g["source_id"]),
            "opponent": g["opponent"],
            "user_color": g["user_color"],
            "user_result": g["user_result"],
            "time_control": g["time_control"],
            "end_time": g["end_time"],
            "analysed": analyses.get(g["source_id"]) is not None,
        }
        for g in rows
    ]


def review_synced_game(gid: str) -> dict:
    games, analyses = _stores()
    game = next((g for g in games.all() if game_id(g["source_id"]) == gid), None)
    if game is None:
        raise GameError("not_found", f"no synced game {gid}")
    engine = get_engine()
    analysis = analyses.get(game["source_id"])
    if analysis is None:  # not in the batch yet: run the fast pass for this one game
        analysis = analyse_game(engine, game["pgn"], BATCH_BUDGET)
        if analysis is None:
            raise GameError("unusable_game", "this game's PGN could not be analysed")
        analyses.add(game["source_id"], analysis)
    return review_game(engine, game, analysis)
