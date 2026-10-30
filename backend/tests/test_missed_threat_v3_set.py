"""Structure and freeze checks for evals/sets/missed_threat_v3. No detector is run here (that would break the label rule's independence)."""

import ast
import hashlib
import json
import re
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "evals" / "sets" / "missed_threat_v3"
BUILDERS = [ROOT / "evals" / "tools" / n for n in ("build_missed_threat_set_v3.py", "freeze_missed_threat_v3.py", "lichess_stream_sample.py")]


def rows(name="positions.jsonl"):
    return [json.loads(x) for x in (SET / name).read_text().splitlines() if x.strip()]


def test_the_builders_import_nothing_from_the_detectors():
    for b in BUILDERS:
        tree = ast.parse(b.read_text())
        mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
        mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not [m for m in mods if m.startswith("app.detectors")], b.name


def test_the_frozen_set_is_well_formed_and_has_no_uncertain_items():
    data = rows()
    assert len(data) == 84 and len({r["id"] for r in data}) == 84
    assert len({(r["fen"], r["move_uci"]) for r in data}) == 84
    assert {r["label"] for r in data} == {"missed", "met", "not_applicable"}
    for r in data:
        b = chess.Board(r["fen"])
        m = chess.Move.from_uci(r["move_uci"])
        assert b.is_valid() and m in b.legal_moves and b.san(m) == r["move_san"] and not b.is_check()
        assert r["ply"] == 2 * (b.fullmove_number - 1) + (0 if b.turn else 1) and r["ply"] >= 4 and not r["constructed"]
        assert r["game"].startswith("https://lichess.org/")


def test_the_uncertain_items_are_kept_apart_and_never_in_the_frozen_set():
    apart = rows("uncertain_unverified.jsonl")
    assert len(apart) == 15 and {r["label"] for r in apart} == {"uncertain"}
    assert not {(r["fen"], r["move_uci"]) for r in apart} & {(r["fen"], r["move_uci"]) for r in rows()}


def test_a_frozen_file_never_changes():
    text = (SET / "FROZEN.md").read_text()
    for name in ("positions.jsonl", "LABEL_RULE.md", "provenance.json"):
        want = re.search(rf"`{re.escape(name)}` \| `([0-9a-f]{{64}})`", text).group(1)
        assert hashlib.sha256((SET / name).read_bytes()).hexdigest() == want, f"{name} changed after the freeze"
