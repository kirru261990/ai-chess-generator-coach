from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from app.api import synced, tools
from app.core.game import GameError
from app.engine.shared import close_engine
from app.engine.stockfish import EngineError


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_engine()


app = FastAPI(title="AI Chess Coach", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATUS = {"not_found": 404, "revision_conflict": 409, "not_your_turn": 409}


@app.exception_handler(GameError)
async def game_error_handler(_: Request, exc: GameError):
    return JSONResponse({"error": exc.code, "message": str(exc)}, _STATUS.get(exc.code, 400))


@app.exception_handler(EngineError)
async def engine_error_handler(_: Request, exc: EngineError):
    return JSONResponse({"error": exc.code, "message": str(exc)}, 503)


class StartGame(BaseModel):
    color: str = "white"
    mode: str = "play"
    level: int = 3


class MoveIn(BaseModel):
    uci: str
    expected_revision: int
    engine_reply: bool = True  # false lets a client show its own move first, then call /engine-move


@app.post("/games")
def start_game(body: StartGame):
    return tools.start_game(body.color, body.mode, body.level)


@app.get("/games/{game_id}")
def get_game(game_id: str):
    return tools.get_game(game_id)


@app.post("/games/{game_id}/moves")
def make_move(game_id: str, body: MoveIn):
    return tools.apply_move(game_id, body.uci, body.expected_revision, body.engine_reply)


@app.get("/synced-games")
def synced_games(limit: int = 20):
    return synced.list_synced_games(limit)


@app.get("/synced-games/{gid}/review")
def synced_game_review(gid: str):
    return synced.review_synced_game(gid)


class ModeIn(BaseModel):
    mode: str


@app.post("/games/{game_id}/mode")
def switch_mode(game_id: str, body: ModeIn):
    return tools.switch_mode(game_id, body.mode)


@app.post("/games/{game_id}/engine-move")
def engine_move(game_id: str):
    return tools.engine_reply(game_id)


@app.post("/games/{game_id}/resign")
def resign(game_id: str):
    return tools.resign_game(game_id)


@app.get("/games/{game_id}/pgn", response_class=PlainTextResponse)
def pgn(game_id: str):
    return tools.export_pgn(game_id)
