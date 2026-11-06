"""Drill cycle routes (ADR 0018). Thin: every rule lives in `app/learner/drillcycle.py`."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.learner import drillcycle as C

CycleError = C.CycleError  # for `main.py`'s error handler
router = APIRouter(prefix="/drills/cycles")

STATUS = {
    "no_drill_bank": 409,
    "drill_bank_too_small": 409,
    "not_current_position": 409,
    "already_answered": 409,
    "illegal_move": 400,
}


def db() -> Iterator:
    conn = C.connect()
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(db)]


class AnswerIn(BaseModel):
    drill_id: str
    move: str


@router.get("")
def overview(conn: Conn):
    return C.summary(conn)


@router.get("/current")
def current(conn: Conn):
    return C.current(conn)


@router.post("/current/answer")
def answer(body: AnswerIn, conn: Conn):
    return C.answer(conn, body.drill_id, body.move)
