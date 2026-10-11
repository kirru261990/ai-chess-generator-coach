"""Training sessions (T44, spec D3 to D5): five positions, the hint ladder, and a log of attempts.

State: sessions live in memory (like games today); every session start and every attempt is also appended to
`data/training/` (git-ignored), so progress, "seen recently" and the 7-day retest survive a restart.

Honest measurement (AGENTS rule 4):
- an attempt made after any hint step (the scan prompt included) is `assisted` for good
- the held-out position gets no hints and exactly one attempt
- the clean signals are `first_try` and not assisted: "first-try accuracy" and the held-out pass rate

Nothing here uses a language model.
"""

from __future__ import annotations

import json
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import chess

from app import config
from app.core.game import GameError
from app.detectors import hanging_own
from app.learner import bank as bank_mod
from app.learner.feedback import PIECE
from app.learner.hints import MAX_LEVEL, consequences, ladder

RETEST_AFTER = timedelta(days=7)
AVOID_RECENT_SESSIONS = 6
MATE_CP = 10_000


def cp_value(score) -> int:
    """A Score as centipawns for its own side; a forced mate counts as a huge win or loss."""
    if score.mate is not None:
        return MATE_CP if score.mate_sign == 1 else -MATE_CP
    return score.cp


def engine_loss(engine, board: chess.Board, move: chess.Move, budget) -> int:
    """Centipawns the side to move gives up by playing `move` instead of the engine's best (never negative)."""
    best = engine.analyse(board, budget, perspective=board.turn)
    after = board.copy()
    after.push(move)
    if after.is_checkmate():
        return 0
    reply = engine.analyse(after, budget, perspective=board.turn)
    return max(0, cp_value(best.score) - cp_value(reply.score))


class Trainer:
    def __init__(self, data_dir: Path | None = None, engine_getter: Callable | None = None,
                 now: Callable[[], datetime] | None = None, budget=None):
        self.data_dir = Path(data_dir) if data_dir else config.DATA_DIR
        self.engine_getter = engine_getter
        self.now = now or (lambda: datetime.now(UTC))
        self.budget = budget
        self.sessions: dict[str, dict] = {}
        self.lock = threading.Lock()
        self._bank: dict | None = None

    # ---- storage
    @property
    def bank(self) -> dict:
        if self._bank is None:
            path = self.data_dir / "bank" / "bank_v1.json"
            if not path.exists():
                raise GameError("not_found", "no practice bank yet: run `uv run python -m app.learner.bank build`")
            bank = json.loads(path.read_text())
            bank_mod.validate(bank)
            self._bank = bank
        return self._bank

    def _log(self, name: str, record: dict) -> None:
        path = self.data_dir / "training" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    def _read(self, name: str) -> list[dict]:
        path = self.data_dir / "training" / name
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    # ---- sessions
    def start(self, motif: str) -> dict:
        sessions, attempts = self._read("sessions.jsonl"), self._read("attempts.jsonl")
        recent = sessions[-AVOID_RECENT_SESSIONS:]
        avoid = frozenset(i for s in recent for i in s["items"])
        by_id = {i["id"]: i for i in self.bank["own"] + self.bank["puzzles"]}
        retest = tuple(by_id[i] for i in self.retest_due(attempts) if i in by_id)
        seed = secrets.randbits(32)
        try:
            items = bank_mod.new_session(self.bank, motif, seed, avoid, retest)
        except bank_mod.BankError as e:
            raise GameError("bank_too_small", str(e)) from e
        sid = secrets.token_hex(5)
        session = {"id": sid, "motif": motif, "seed": seed, "created_at": self.now().isoformat(timespec="seconds"),
                   "items": items, "hints": {}, "done": {}, "attempts": {}}
        with self.lock:
            self.sessions[sid] = session
        self._log("sessions.jsonl", {"id": sid, "motif": motif, "seed": seed, "at": session["created_at"],
                                      "items": [i["id"] for i in items], "bank_version": self.bank["bank_version"]})
        return self.view(session)

    def get(self, sid: str) -> dict:
        session = self.sessions.get(sid)
        if session is None:
            raise GameError("not_found", "no such training session")
        return session

    def view(self, session: dict) -> dict:
        return {
            "id": session["id"], "motif": session["motif"], "motif_label": bank_mod.MOTIF_LABEL[session["motif"]],
            "items": [{**bank_mod.public_item(n, i), "done": n in session["done"]} for n, i in enumerate(session["items"])],
        }

    def _item(self, session: dict, index: int) -> dict:
        if not 0 <= index < len(session["items"]):
            raise GameError("not_found", "no such position in this session")
        return session["items"][index]

    # ---- hints
    def hint(self, sid: str, index: int, level: int) -> dict:
        session = self.get(sid)
        item = self._item(session, index)
        if item["kind"] == "held_out":
            raise GameError("hint_not_allowed", "the test position has no hints")
        if index in session["done"]:
            raise GameError("item_done", "this position is finished")
        level = max(1, min(MAX_LEVEL, level))
        result = ladder(chess.Board(item["fen"]), item["answer"], level)
        with self.lock:
            session["hints"][index] = max(session["hints"].get(index, 0), result["level"])
        return {"index": index, "hints_used": session["hints"][index], **result}

    # ---- attempts
    def attempt(self, sid: str, index: int, uci: str) -> dict:
        session = self.get(sid)
        item = self._item(session, index)
        with self.lock:
            if index in session["done"]:
                raise GameError("item_done", "this position is finished")
            tries = session["attempts"].get(index, 0)
        board = chess.Board(item["fen"])
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            move = None
        if move is None or move not in board.legal_moves:
            raise GameError("illegal_move", f"{uci} is not a legal move here")
        loss = None
        if uci != item["answer"] and self.engine_getter is not None:
            try:  # an engine problem must not turn a good move into a wrong one: only the stored answer counts then
                loss = engine_loss(self.engine_getter(), board, move, self.budget)
            except Exception:  # noqa: BLE001
                loss = None
        verdict = bank_mod.check_move(item, uci, loss)
        hints_used = session["hints"].get(index, 0)
        record = {
            "at": self.now().isoformat(timespec="seconds"), "session": sid, "item": item["id"], "source": item["source"],
            "motif": item["motif"], "kind": item["kind"], "uci": uci, "correct": verdict["correct"],
            "accepted_by": verdict["accepted_by"], "loss_cp": verdict.get("loss_cp", loss),
            "first_try": tries == 0, "hints_used": hints_used, "assisted": hints_used > 0,
        }
        with self.lock:
            session["attempts"][index] = tries + 1
            finished = verdict["correct"] or item["kind"] == "held_out"  # the test position gets exactly one attempt
            if finished:
                session["done"][index] = record
        self._log("attempts.jsonl", record)
        out = {"index": index, "correct": verdict["correct"], "accepted_by": verdict["accepted_by"],
               "first_try": record["first_try"], "assisted": record["assisted"], "finished": finished,
               "facts": self._facts(board, move, item, verdict["correct"])}
        if finished:
            out["answer"] = self._answer(board, item)
        return out

    def give_up(self, sid: str, index: int) -> dict:
        """Show the answer and its reason, and count the position as missed."""
        session = self.get(sid)
        item = self._item(session, index)
        if item["kind"] == "held_out":
            raise GameError("hint_not_allowed", "the test position has no answer on request")
        with self.lock:
            if index in session["done"]:
                raise GameError("item_done", "this position is finished")
        board = chess.Board(item["fen"])
        record = {
            "at": self.now().isoformat(timespec="seconds"), "session": sid, "item": item["id"], "source": item["source"],
            "motif": item["motif"], "kind": item["kind"], "uci": None, "correct": False, "accepted_by": None,
            "loss_cp": None, "first_try": session["attempts"].get(index, 0) == 0,
            "hints_used": MAX_LEVEL, "assisted": True, "gave_up": True,
        }
        with self.lock:
            session["done"][index] = record
        self._log("attempts.jsonl", record)
        return {"index": index, "finished": True, "answer": self._answer(board, item)}

    @staticmethod
    def _answer(board: chess.Board, item: dict) -> dict:
        move = chess.Move.from_uci(item["answer"])
        return {"uci": item["answer"], "san": board.san(move), "why": " ".join(consequences(board, move)),
                **({"played_san": board.san(chess.Move.from_uci(item["played"]))} if item.get("played") else {})}

    @staticmethod
    def _facts(board: chess.Board, move: chess.Move, item: dict, correct: bool) -> list[str]:
        """Checked facts about the move the player chose (rules and the `hanging_own` detector), never opinions."""
        if correct:
            return consequences(board, move)
        after = board.copy()
        after.push(move)
        us = board.turn
        facts = []
        for h in hanging_own.hanging_pieces(after, us):
            facts.append(f"After this move your {PIECE[h.piece.lower()]} on {h.square} can be taken.")
        if after.is_checkmate():
            facts.append("It is checkmate.")
        if not facts:
            facts.append("That is not the move this position is looking for. Try again, or ask for a hint.")
        return facts

    # ---- progress
    @staticmethod
    def retest_due(attempts: list[dict], now: datetime | None = None, after: timedelta = RETEST_AFTER) -> list[str]:
        """Item ids whose first try was wrong at least `after` ago and that have not been solved cleanly since."""
        now = now or datetime.now(UTC)
        due = {}
        for a in attempts:
            if a["kind"] == "held_out":
                continue
            when = datetime.fromisoformat(a["at"])
            if a["first_try"] and not a["correct"] and now - when >= after:
                due[a["item"]] = when
            elif a["correct"] and not a["assisted"] and a["item"] in due and when > due[a["item"]]:
                del due[a["item"]]
        return sorted(due)

    def progress(self) -> dict:
        """First-try accuracy (unassisted) and the held-out pass rate, per motif, as k/n with the counts shown."""
        attempts = self._read("attempts.jsonl")
        out = {"sessions": len(self._read("sessions.jsonl")), "by_motif": {}}
        for motif in bank_mod.OWN_MOTIFS:
            mine = [a for a in attempts if a["motif"] == motif]
            practice_first = [a for a in mine if a["kind"] != "held_out" and a["first_try"] and not a.get("gave_up")]
            held = [a for a in mine if a["kind"] == "held_out"]
            unassisted_held = [a for a in held if not a["assisted"]]
            out["by_motif"][motif] = {
                "practice_first_tries": len(practice_first),
                "practice_first_try_correct": sum(a["correct"] for a in practice_first),
                "practice_first_try_correct_unassisted": sum(a["correct"] and not a["assisted"] for a in practice_first),
                "held_out_attempts": len(unassisted_held),
                "held_out_correct": sum(a["correct"] for a in unassisted_held),
            }
        out["retest_due"] = len(self.retest_due(attempts, self.now()))
        return out


TRAINER = Trainer()
