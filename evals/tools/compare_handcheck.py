"""Compare a person's hand-check answers with the items' `material_label` (LABEL_RULE.md section 9).

Usage:  cd backend && uv run python ../evals/tools/compare_handcheck.py ../evals/sets/real_play_v1/handchecks/owner_answers.txt

Answer lines look like `rp1-201: A yes, B no`. This is the owner's two-question format:
  missed_free: A no -> not_applicable;  A yes + B yes -> taken;  A yes + B no -> missed
  hanging_own: A yes -> missed;         A no -> taken
"can't tell" answers are listed and excluded (they are replaced, not counted as agreement).
Every disagreement is adjudicated by the builder's independent exchange search (not a detector): the label is
"supported" if that search gives the same material outcome. No detector is run here.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import chess

SET = Path(__file__).resolve().parents[1] / "sets" / "real_play_v1"
BUILDER = Path(__file__).resolve().parent / "build_real_play_set.py"
NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen"}


def parse(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*(rp1-\d+)\s*:\s*(.*)$", line)
        if not m:
            continue
        out[m.group(1)] = {k: v.strip().lower() for k, v in re.findall(r"([ABC])\s+([^,]+)", m.group(2))}
    return out


def implied(detector, a):
    """The label implied by the owner's answers, or None if it cannot be decided."""
    if a.get("A") not in ("yes", "no"):
        return None
    if detector == "hanging_own":
        return "missed" if a["A"] == "yes" else "taken"
    if a["A"] == "no":
        return "not_applicable"
    if a.get("B") == "yes":
        return "taken"
    if a.get("B") == "no":
        return "missed"
    return None


def adjudicate(r):
    """Material outcome of the item from the independent search alone, plus the facts behind it."""
    spec = importlib.util.spec_from_file_location("build_real_play_set", BUILDER)
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    board = chess.Board(r["fen"])
    move = chess.Move.from_uci(r["move_uci"])
    if r["detector"] == "hanging_own":
        gain = b.hang_gain_after(board, move)
        return ("missed" if gain >= b.MIN_GAIN else "taken"), f"after the move the opponent's best capture nets {gain:+d}"
    caps = sorted(((b.capture_net(board, m), board.san(m), NAMES[board.piece_at(m.to_square).piece_type])
                   for m in board.legal_moves if b.capture_net(board, m) != 0), reverse=True)
    best = b.best_capture_net(board)
    facts = "; ".join(f"{san} takes the {victim} (net {net:+d})" for net, san, victim in caps[:3]) or "no capture wins material"
    if best < b.MIN_GAIN:
        return "not_applicable", facts
    return ("taken" if b.capture_net(board, move) >= b.MIN_GAIN else "missed"), facts


def compare(answers, rows):
    results = []
    for item_id, a in answers.items():
        r = rows[item_id]
        got = implied(r["detector"], a)
        results.append({"id": item_id, "detector": r["detector"], "category": r["category"],
                        "expected": r["material_label"], "implied": got, "answers": a,
                        "agree": None if got is None else got == r["material_label"]})
    return results


def main(path):
    rows = {r["id"]: r for r in map(json.loads, (SET / "positions.jsonl").read_text().splitlines())}
    results = compare(parse(Path(path).read_text()), rows)
    decided = [r for r in results if r["agree"] is not None]
    disagree = [r for r in decided if not r["agree"]]
    print(f"items answered: {len(results)} | decided: {len(decided)} | can't tell: {len(results) - len(decided)}")
    print(f"agree: {len(decided) - len(disagree)} of {len(decided)} | disagree: {len(disagree)}")
    by = {}
    for r in decided:
        d = by.setdefault((r["detector"], r["category"]), [0, 0])
        d[0] += r["agree"]
        d[1] += 1
    for (det, cat), (ok, n) in sorted(by.items()):
        print(f"  {det:12} {cat:22} {ok}/{n}")
    supported = 0
    for r in disagree:
        label, facts = adjudicate(rows[r["id"]])
        ok = label == r["expected"]
        supported += ok
        print(f"DISAGREE {r['id']} ({r['detector']}, {r['category']}): label {r['expected']}, answers imply {r['implied']}")
        print(f"   independent check says {label} ({facts}) -> label {'SUPPORTED' if ok else 'NOT supported'}")
    if disagree:
        print(f"adjudication: label supported in {supported} of {len(disagree)} disagreements")
    return results


if __name__ == "__main__":
    main(sys.argv[1])
