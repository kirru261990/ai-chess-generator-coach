"""Opening repertoire routes (ADR 0022). Thin: every rule lives in `app/learner/repdrill.py` and `repertoire.py`. Practice only."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

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
    move: str


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
                "unchecked": book_unchecked(book),
            }
        out.append(row)
    return {"openings": out, "assisted_only": True}


def book_unchecked(book: dict) -> bool:
    return any(n.get("check", {}).get("status") == "unchecked" for n in book["nodes"].values())


@router.post("/{key}/runs")
def start(key: str, conn: Conn):
    return D.start(conn, key, _book(key))


@router.post("/{key}/runs/{run_id}/answer")
def answer(key: str, run_id: int, body: AnswerIn, conn: Conn):
    return D.answer(conn, run_id, body.move, _book(key))
