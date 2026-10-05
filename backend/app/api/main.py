from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from app.api import tools
from app.core.game import GameError

app = FastAPI(title="AI Chess Coach")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATUS = {"not_found": 404, "revision_conflict": 409}


@app.exception_handler(GameError)
async def game_error_handler(_: Request, exc: GameError):
    return JSONResponse({"error": exc.code, "message": str(exc)}, _STATUS.get(exc.code, 400))


class StartGame(BaseModel):
    color: str = "white"
    mode: str = "play"


class MoveIn(BaseModel):
    uci: str
    expected_revision: int


@app.post("/games")
def start_game(body: StartGame):
    return tools.start_game(body.color, body.mode)


@app.get("/games/{game_id}")
def get_game(game_id: str):
    return tools.get_game(game_id)


@app.post("/games/{game_id}/moves")
def make_move(game_id: str, body: MoveIn):
    return tools.apply_move(game_id, body.uci, body.expected_revision)


@app.post("/games/{game_id}/resign")
def resign(game_id: str):
    return tools.resign_game(game_id)


@app.get("/games/{game_id}/pgn", response_class=PlainTextResponse)
def pgn(game_id: str):
    return tools.export_pgn(game_id)
