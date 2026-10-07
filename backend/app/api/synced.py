"""Tools over synced (real) games: list them and review one (spec §06 review_game)."""

import chess

from app import config
from app.coach.intent import clean_answer, compare, mate_flags, moment_facts
from app.coach.intent_store import save as save_intent
from app.core.game import GameError
from app.engine.batch import BATCH_BUDGET, SCHEMA, AnalysisStore, analyse_game, game_id
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
            "analysed": analyses.has_current_schema(g["source_id"]),
        }
        for g in rows
    ]


def review_synced_game(gid: str) -> dict:
    games, analyses = _stores()
    game = next((g for g in games.all() if game_id(g["source_id"]) == gid), None)
    if game is None:
        raise GameError("not_found", f"no synced game {gid}")
    engine = get_engine()
    # Reuse the stored fast pass only if this engine, budget and record layout produced it.
    # Otherwise (missing, older engine, shallower budget, old layout) analyse again.
    if analyses.has(game["source_id"], engine.name, BATCH_BUDGET):
        analysis = analyses.get(game["source_id"])
    else:
        analysis = analyse_game(engine, game["pgn"], BATCH_BUDGET)
        if analysis is None:
            raise GameError("unusable_game", "this game's PGN could not be analysed")
        analyses.add(game["source_id"], analysis)
    return review_game(engine, game, analysis)


def _moment(gid: str, ply: int) -> tuple[dict, dict, str, str]:
    """(game, analysis, FEN before, move) for the user's move at `ply`, from the stored fast pass."""
    games, analyses = _stores()
    game = next((g for g in games.all() if game_id(g["source_id"]) == gid), None)
    if game is None:
        raise GameError("not_found", f"no synced game {gid}")
    analysis = analyses.get(game["source_id"])
    if analysis is None or analysis.get("schema") != SCHEMA:
        raise GameError("not_analysed", "review this game first so it has been analysed")
    moves = analysis["moves"]
    white = game["user_color"] == "white"
    if not 0 <= ply < len(moves) or (ply % 2 == 0) != white:
        raise GameError("invalid_ply", "that is not one of your moves")
    return game, analysis, analysis["positions"][ply]["fen"], moves[ply]


def moment_intent(gid: str, ply: int, answer: str | None, drafter) -> dict:
    """Compare the player's own words about a key moment with the facts that were on the board (T19)."""
    game, _, fen, uci = _moment(gid, ply)
    user = chess.WHITE if game["user_color"] == "white" else chess.BLACK
    answer = clean_answer(answer)
    facts = moment_facts(fen, user, uci, mate_flags(get_engine(), fen, user, uci))
    comparison = compare(drafter, answer, facts)
    if answer:
        save_intent(gid, ply, answer, comparison, facts)
    return {"ply": ply, "answer": answer, "facts": facts, "self_reported": True, **comparison}
