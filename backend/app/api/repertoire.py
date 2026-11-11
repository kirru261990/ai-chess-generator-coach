"""Opening repertoire routes (ADR 0022). Thin: every rule lives in `app/learner/repdrill.py` and `repertoire.py`. Practice only."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.learner import repdrill as D
from app.learner import repertoire
from app.learner.openingtrie import OPENINGS

DrillError = D.DrillError  # for `main.py`'s error handler
router = APIRouter(prefix="/repertoire")

STATUS = {
    "unknown_opening": 404,
    "book_missing": 409,
    "no_lines": 409,
    "no_such_run": 404,
    "run_finished": 409,
    "stale_question": 409,
    "illegal_move": 400,
}


def db() -> Iterator:
    conn = D.connect()
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(db)]


class AnswerIn(BaseModel):
    move: str = Field(min_length=4, max_length=5)  # a move in UCI, e.g. e2e4 or e7e8q
    ply: int = Field(
        ge=0
    )  # the question's ply: an answer to a question that was already answered is refused, not counted twice


def _book(key: str) -> dict:
    if key not in OPENINGS:
        raise D.DrillError("unknown_opening", f"{key} is not one of the repertoire openings")
    book = repertoire.load_book(key)
    if book is None:
        raise D.DrillError("book_missing", f"no book has been built for {OPENINGS[key].name} yet")
    return book


@router.get("")
def overview(conn: Conn):
    out = []
    for key, o in OPENINGS.items():
        book = repertoire.load_book(key)
        row = {"key": key, "name": o.name, "side": o.side, "available": book is not None}
        if book is not None:
            row |= {k: v for k, v in D.stats(conn, key, book).items() if k != "key"}
            row |= {
                "games": book["games"],
                "stopped": len(book["stopped"]),
                "unchecked": not repertoire.is_checked(book),
            }
        out.append(row)
    return {"openings": out, "assisted_only": True}


@router.post("/{key}/runs")
def start(key: str, conn: Conn, learn: bool = True):
    """`learn` (default) shows the move as an arrow; `learn=false` is a recall run that names nothing before the answer."""
    return D.start(conn, key, _book(key), learn=learn)


@router.post("/{key}/runs/{run_id}/answer")
def answer(key: str, run_id: int, body: AnswerIn, conn: Conn):
    return D.answer(conn, run_id, body.move, _book(key), key=key, ply=body.ply)


@router.get("/{key}/runs/{run_id}")
def current(key: str, run_id: int, conn: Conn):
    return D.current(conn, run_id, _book(key), key=key)
