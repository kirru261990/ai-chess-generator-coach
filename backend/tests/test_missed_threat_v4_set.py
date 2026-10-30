"""Structure and freeze checks for evals/sets/missed_threat_v4. No detector is run here."""

import ast
import hashlib
import json
import re
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "evals" / "sets" / "missed_threat_v4"
V3 = ROOT / "evals" / "sets" / "missed_threat_v3"
BUILDERS = [ROOT / "evals" / "tools" / n for n in ("build_missed_threat_set_v4.py", "freeze_missed_threat_v4.py")]


def rows(d=SET):
    return [json.loads(x) for x in (d / "positions.jsonl").read_text().splitlines() if x.strip()]


def test_the_builders_import_nothing_from_the_detectors():
    for b in BUILDERS:
        tree = ast.parse(b.read_text())
        mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
        mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not [m for m in mods if m.startswith("app.detectors")], b.name


def test_the_frozen_set_is_well_formed_and_has_no_uncertain_items():
    data = rows()
    assert len(data) == 88 and len({r["id"] for r in data}) == 88
    assert {r["label"] for r in data} == {"missed", "met", "not_applicable"}
    for r in data:
        b = chess.Board(r["fen"])
        m = chess.Move.from_uci(r["move_uci"])
        assert b.is_valid() and m in b.legal_moves and b.san(m) == r["move_san"] and not b.is_check() and r["ply"] >= 4
        assert r["game"].startswith("https://lichess.org/")


def test_no_game_or_position_is_shared_with_missed_threat_v3():
    v3 = {r["game"] for r in rows(V3)} | {json.loads(x)["game"] for x in (V3 / "uncertain_unverified.jsonl").read_text().splitlines()}
    assert not v3 & {r["game"] for r in rows()}
    assert not {(r["fen"], r["move_uci"]) for r in rows(V3)} & {(r["fen"], r["move_uci"]) for r in rows()}


def test_a_frozen_file_never_changes():
    text = (SET / "FROZEN.md").read_text()
    for name in ("positions.jsonl", "LABEL_RULE.md", "provenance.json"):
        want = re.search(rf"`{re.escape(name)}` \| `([0-9a-f]{{64}})`", text).group(1)
        assert hashlib.sha256((SET / name).read_bytes()).hexdigest() == want, f"{name} changed after the freeze"
