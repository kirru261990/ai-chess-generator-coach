"""Compare a person's hand-check answers with the items' `material_label` (LABEL_RULE.md section 9).

Usage:  cd backend && uv run python ../evals/tools/compare_handcheck.py ANSWERS [--full] [--engine-items FILE]
  (default is the owner's two-question page; --full is the three-question sheet; --engine-items lists ids
  answered with an engine, so tool-assisted answers are reported separately)

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


def implied_full(detector, a):
    """The label implied by the three-question sheet (LABEL_RULE.md section 9), or None if undecided."""
    A, B, C = a.get("A"), a.get("B"), a.get("C")
    if A not in ("yes", "no"):
        return None
    if detector == "missed_free":
        if A == "no":
            return "not_applicable"
        if B == "yes":
            return "taken"
        if B == "no" and C in ("yes", "no"):
            return "uncertain" if C == "yes" else "missed"
        return None
    if A == "yes":
        return {"yes": "missed", "no": "not_applicable"}.get(B)
    return {"yes": "taken", "no": "not_applicable"}.get(C)


def implied(detector, a, full=False):
    """The label implied by the answers, or None if it cannot be decided."""
    if full:
        return implied_full(detector, a)
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
        flags = b.choice_flags(board)
        hangs, safe, unsafe = flags[move], any(not v for v in flags.values()), any(flags.values())
        label = ("missed" if safe else "not_applicable") if hangs else ("taken" if unsafe else "not_applicable")
        return label, (f"the move {'hangs' if hangs else 'does not hang'} a piece; a safe alternative "
                       f"{'exists' if safe else 'does not exist'}; some move would hang a piece: {unsafe}")
    caps = sorted(((b.capture_net(board, m), board.san(m), NAMES[board.piece_at(m.to_square).piece_type])
                   for m in board.legal_moves if b.capture_net(board, m) != 0), reverse=True)
    best = b.best_capture_net(board)
    facts = "; ".join(f"{san} takes the {victim} (net {net:+d})" for net, san, victim in caps[:3]) or "no capture wins material"
    if best < b.MIN_GAIN:
        return "not_applicable", facts
    if b.capture_net(board, move) >= b.MIN_GAIN:
        return "taken", facts
    after = board.copy()
    after.push(move)
    if after.is_checkmate():  # a mate that skips the capture: material says missed, but mate matters more
        return "uncertain", facts + "; the move is checkmate"
    return "missed", facts


def compare(answers, rows, full=False):
    results = []
    for item_id, a in answers.items():
        r = rows[item_id]
        got = implied(r["detector"], a, full)
        results.append({"id": item_id, "detector": r["detector"], "category": r["category"],
                        "expected": r["material_label"], "implied": got, "answers": a,
                        "agree": None if got is None else got == r["material_label"]})
    return results


def main(path, full=False, engine_file=None):
    rows = {r["id"]: r for r in map(json.loads, (SET / "positions.jsonl").read_text().splitlines())}
    results = compare(parse(Path(path).read_text()), rows, full)
    if engine_file:
        eng = set(Path(engine_file).read_text().split())
        for label, pick in (("engine-assisted", True), ("python-chess only", False)):
            sub = [r for r in results if (r["id"] in eng) == pick and r["agree"] is not None]
            print(f"{label}: {sum(r['agree'] for r in sub)} of {len(sub)} agree")
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
    for r in results:
        if r["agree"] is None:
            print(f"  undecided {r['id']} ({r['detector']}, {r['category']}): answers {r['answers']}, label {r['expected']}")
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
    args = sys.argv[1:]
    engine = args[args.index("--engine-items") + 1] if "--engine-items" in args else None
    main(args[0], "--full" in args, engine)
