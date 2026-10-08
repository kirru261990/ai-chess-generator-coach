"""Structure and freeze checks for evals/sets/e2_v1. No coach, detector or model is run here."""

import ast
import hashlib
import json
import re
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "evals" / "sets" / "e2_v1"
BUILDER = ROOT / "evals" / "tools" / "build_e2_set.py"
FROZEN = SET / "FROZEN.md"
PROMPTS_V1 = {
    "evals/sets/e2_v1/positions.jsonl": SET / "positions.jsonl",
    "evals/sets/e2_v1/provenance.json": SET / "provenance.json",
    "evals/tools/prompts/extract_v1.md": ROOT / "evals/tools/prompts/extract_v1.md",
    "evals/tools/prompts/raw_v1.md": ROOT / "evals/tools/prompts/raw_v1.md",
    "backend/app/coach/prompts/why_v1.md": ROOT / "backend/app/coach/prompts/why_v1.md",
}


SET_V2 = ROOT / "evals" / "sets" / "e2_v2"
PROMPTS_V2 = {
    "evals/sets/e2_v2/positions.jsonl": SET_V2 / "positions.jsonl",
    "evals/sets/e2_v2/provenance.json": SET_V2 / "provenance.json",
    "evals/tools/prompts/extract_v2.md": ROOT / "evals/tools/prompts/extract_v2.md",
    "evals/tools/prompts/raw_v1.md": ROOT / "evals/tools/prompts/raw_v1.md",
    "backend/app/coach/prompts/why_v2.md": ROOT / "backend/app/coach/prompts/why_v2.md",
}


def rows(directory=SET):
    return [json.loads(line) for line in (directory / "positions.jsonl").read_text().splitlines() if line.strip()]


def test_the_builder_imports_neither_detectors_nor_the_coach():
    tree = ast.parse(BUILDER.read_text())
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in modules if m.startswith(("app.detectors", "app.coach"))]


def test_the_set_has_the_promised_shape():
    items = rows()
    assert len(items) == 50
    assert sum(i["kind"] == "good" for i in items) == 25 and sum(i["kind"] == "bad" for i in items) == 25
    assert len({i["id"] for i in items}) == 50 and len({i["puzzle_id"] for i in items}) == 50
    for i in items:
        board = chess.Board(i["fen"])
        assert chess.Move.from_uci(i["move_uci"]) in board.legal_moves
        assert board.san(chess.Move.from_uci(i["move_uci"])) == i["move_san"]
        assert i["user_color"] == ("white" if board.turn == chess.WHITE else "black")
        assert 400 <= i["rating"] <= 1199
        assert i["kind"] == "good" and i["engine_loss_cp"] <= 50 or i["kind"] == "bad" and 150 <= i["engine_loss_cp"] <= 600


def test_no_mate_themed_puzzle_is_in_the_set():
    assert not [i for i in rows() if any(t.startswith("mate") for t in i["themes"])]


def test_frozen_files_have_not_changed():
    for frozen, files in ((FROZEN, PROMPTS_V1), (SET_V2 / "FROZEN.md", PROMPTS_V2)):
        check_frozen(frozen, files)


def test_the_v2_set_is_new_and_has_the_same_shape():
    v1, v2 = rows(SET), rows(SET_V2)
    assert len(v2) == 50 and not {i["puzzle_id"] for i in v1} & {i["puzzle_id"] for i in v2}
    assert sum(i["kind"] == "good" for i in v2) == 25 and len({i["id"] for i in v2}) == 50
    for i in v2:
        board = chess.Board(i["fen"])
        assert chess.Move.from_uci(i["move_uci"]) in board.legal_moves
        assert not any(t.startswith("mate") for t in i["themes"])


def check_frozen(frozen, files):
    text = frozen.read_text()
    for name, path in files.items():
        recorded = re.search(rf"`{re.escape(name)}`\s*\|\s*`([0-9a-f]{{64}})`", text)
        assert recorded, f"{name} is not recorded in FROZEN.md"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == recorded.group(1), f"{name} changed after the freeze"
