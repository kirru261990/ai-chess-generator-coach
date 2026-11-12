from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.api import access, blind_spots, coach, drills, repertoire, slip_rounds, synced, tools
from app.coach import usage
from app.core.game import GameError
from app.engine.shared import close_engine
from app.engine.stockfish import EngineError
from app.learner import lossmap


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_engine()


app = FastAPI(title="AI Chess Coach", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # Local development only: Vite moves to 5174, 5175... when a port is busy.
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)
# Outermost: from outside this Mac (a tunnel) every request needs the access password (ADR 0023).
app.add_middleware(access.AccessGate)

_STATUS = {
    "not_found": 404,
    "baseline_invalid": 500,
    "feedback_not_allowed": 403,
    "revision_conflict": 409,
    "not_your_turn": 409,
    "takeback_not_allowed": 409,
    "nothing_to_take_back": 409,
    "no_hint": 409,
}


@app.exception_handler(GameError)
async def game_error_handler(_: Request, exc: GameError):
    return JSONResponse({"error": exc.code, "message": str(exc)}, _STATUS.get(exc.code, 400))


@app.exception_handler(EngineError)
async def engine_error_handler(_: Request, exc: EngineError):
    return JSONResponse({"error": exc.code, "message": str(exc)}, 503)


@app.exception_handler(coach.AssessmentError)
async def assessment_error_handler(_: Request, exc: coach.AssessmentError):
    return JSONResponse({"error": exc.code, "message": str(exc)}, coach.STATUS.get(exc.code, 400))


@app.exception_handler(repertoire.DrillError)
async def repertoire_error_handler(_: Request, exc: repertoire.DrillError):
    return JSONResponse({"error": exc.code, "message": exc.message}, repertoire.STATUS.get(exc.code, 400))


@app.exception_handler(slip_rounds.RoundError)
async def round_error_handler(_: Request, exc: slip_rounds.RoundError):
    return JSONResponse({"error": exc.code, "message": str(exc)}, slip_rounds.STATUS.get(exc.code, 400))


@app.exception_handler(drills.CycleError)
async def cycle_error_handler(_: Request, exc: drills.CycleError):
    return JSONResponse({"error": exc.code, "message": str(exc)}, drills.STATUS.get(exc.code, 400))


app.include_router(coach.router)
app.include_router(drills.router)
app.include_router(slip_rounds.router)
app.include_router(repertoire.router)


class StartGame(BaseModel):
    color: str = "white"
    mode: str = "play"
    level: int = 3
    opponent: str = "stockfish"  # or "maia3" (human-like; needs `elo`)
    elo: int | None = None


class MoveIn(BaseModel):
    uci: str
    expected_revision: int
    engine_reply: bool = True  # false lets a client show its own move first, then call /engine-move


@app.get("/opponents")
def opponents():
    """Which opponents this server can play: Stockfish always, Maia-3 only when installed (ADR 0012)."""
    from app.engine import maia
    return {"maia3": {"available": maia.available(), "min_elo": maia.MIN_ELO, "max_elo": maia.MAX_ELO}}


@app.post("/games")
def start_game(body: StartGame):
    return tools.start_game(body.color, body.mode, body.level, body.opponent, body.elo)


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


@app.get("/blind-spots/baseline")
def baseline_blind_spots():
    return blind_spots.baseline_blind_spots()


@app.get("/loss-map")
def loss_map():
    return lossmap.own()


@app.get("/games/{game_id}/feedback/{ply}")
def move_feedback(game_id: str, ply: int):
    return tools.move_feedback(game_id, ply)


class WhyIn(BaseModel):
    ply: int


@app.post("/games/{game_id}/coach/why")
def coach_why(game_id: str, body: WhyIn):
    return tools.coach_why(game_id, body.ply)


@app.get("/games/{game_id}/eval")
def position_eval(game_id: str):
    return tools.position_eval(game_id)


@app.get("/games/{game_id}/hint")
def hint(game_id: str, level: int = 1):
    return tools.hint(game_id, level)


@app.get("/games/{game_id}/threats")
def current_threats(game_id: str):
    return tools.current_threats(game_id)


@app.get("/usage")
def model_usage():
    """This month's model spend against the budget (estimated from list prices; the Console is the authority)."""
    return usage.summary()


class IntentIn(BaseModel):
    text: str | None = None  # the player's own words; empty or missing means they skipped the question


@app.post("/synced-games/{gid}/moments/{ply}/intent")
def moment_intent(gid: str, ply: int, body: IntentIn):
    return synced.moment_intent(gid, ply, body.text, tools.get_drafter("coach_intent"))


class ModeIn(BaseModel):
    mode: str


@app.post("/games/{game_id}/mode")
def switch_mode(game_id: str, body: ModeIn):
    return tools.switch_mode(game_id, body.mode)


@app.post("/games/{game_id}/engine-move")
def engine_move(game_id: str):
    return tools.engine_reply(game_id)


@app.post("/games/{game_id}/takeback")
def takeback(game_id: str):
    return tools.take_back_move(game_id)


@app.post("/games/{game_id}/resign")
def resign(game_id: str):
    return tools.resign_game(game_id)


@app.get("/games/{game_id}/pgn", response_class=PlainTextResponse)
def pgn(game_id: str):
    return tools.export_pgn(game_id)


# One address for the office (ADR 0023): when the web app has been built (`pnpm build` with VITE_API_URL empty) the API serves it,
# last, so every API route above wins. Without a build this does nothing and Vite serves the page as before.
_WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"
if (_WEB_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="web")
