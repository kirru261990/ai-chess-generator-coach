"""In-memory game store (V1 skeleton). Replaced by Postgres in the learner service."""

from app.core.game import Game

GAMES: dict[str, Game] = {}
