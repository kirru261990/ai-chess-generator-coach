"""First-slip round routes (ADR 0020). Thin: every rule lives in `app/learner/slipround.py`."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.learner import slipround as S

RoundError = S.RoundError  # for `main.py`'s error handler
router = APIRouter(prefix="/drills/rounds")

STATUS = {"no_slip_drills": 409, "round_too_small": 409, "not_current_position": 409, "already_answered": 409, "illegal_move": 400}


def db() -> Iterator:
    conn = S.connect()
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(db)]


class AnswerIn(BaseModel):
    drill_id: str
    move: str


@router.get("/current")
def current(conn: Conn):
    return S.current(conn)


@router.post("/current/answer")
def answer(body: AnswerIn, conn: Conn):
    return S.answer(conn, body.drill_id, body.move)
