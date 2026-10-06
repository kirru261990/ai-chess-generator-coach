"""Score the detectors on the frozen real_play_v1 set (T13). Reads the set; never edits it or the detectors.

Run:  cd backend && uv run python ../evals/tools/score_detectors.py

For each item the detector for that item is run twice:
  static   no engine evidence (what the detector says from the board alone)
  evidence with the engine evidence the production pipeline uses: Stockfish at the fast-pass budget (depth 10),
           best move versus the played move, from the mover's side, mates clamped (app.learner.review.cp_equiv)
Both are scored against the item's `label` (the outcome a correct detector gives WITH evidence; LABEL_RULE.md section 1).

Output: evals/reports/real_play_v1_<date>.json (all numbers and every disagreement) and
        evals/reports/real_play_v1_<date>.md (tables; optional notes appended from ..._notes.md)
"""

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.detectors import hanging_own, missed_free
from app.detectors.hanging_own import Evidence
from app.engine.batch import BATCH_BUDGET
from app.engine.stockfish import Engine
from app.learner.review import cp_equiv

SET = ROOT / "evals" / "sets" / "real_play_v1"
REPORTS = ROOT / "evals" / "reports"
DETECTORS = {"hanging_own": hanging_own, "missed_free": missed_free}
REAL = {"real_taken", "real_blunder", "real_safe", "no_opportunity"}  # real positions from real games
OUTCOMES = ["missed", "taken", "uncertain", "not_applicable"]


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes in n trials (None if n == 0)."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def frac(k, n):
    """'k/n = 0.80 (95% CI 0.55-0.93)' or 'n/a (0 cases)'."""
    if n == 0:
        return "n/a (0 cases)"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.2f} (95% CI {lo:.2f}-{hi:.2f})"


def evidence_for(engine, board, move):
    mover = board.turn
    best = engine.analyse(board, BATCH_BUDGET, perspective=mover)
    after = board.copy()
    after.push(move)
    a = engine.analyse(after, BATCH_BUDGET, perspective=mover)
    return Evidence(
        best_cp=cp_equiv(best.score.cp, best.score.mate, best.score.mate_sign),
        after_cp=cp_equiv(a.score.cp, a.score.mate, a.score.mate_sign),
    )


def run(rows, engine):
    out = []
    for r in rows:
        board = chess.Board(r["fen"])
        move = chess.Move.from_uci(r["move_uci"])
        det = DETECTORS[r["detector"]]
        ev = evidence_for(engine, board, move)
        out.append({
            **{k: r[k] for k in ("id", "detector", "category", "label", "material_label", "fen", "move_san",
                                 "band", "mate_theme", "constructed")},
            "static": det.detect(board, move).outcome,
            "evidence": det.detect(board, move, ev).outcome,
            "evidence_best_cp": ev.best_cp,
            "evidence_after_cp": ev.after_cp,
        })
    return out


def metrics(items, mode):
    """Precision and recall for the `missed` class, plus the confusion matrix."""
    tp = sum(1 for i in items if i["label"] == "missed" and i[mode] == "missed")
    fp = sum(1 for i in items if i["label"] != "missed" and i[mode] == "missed")
    fn = sum(1 for i in items if i["label"] == "missed" and i[mode] != "missed")
    agree = sum(1 for i in items if i["label"] == i[mode])
    conf = Counter((i["label"], i[mode]) for i in items)
    return {"n": len(items), "tp": tp, "fp": fp, "fn": fn, "precision": [tp, tp + fp], "recall": [tp, tp + fn],
            "exact_agreement": [agree, len(items)], "confusion": {f"{a}->{b}": c for (a, b), c in sorted(conf.items())}}


GROUPS = {
    "all items": lambda i: True,
    "real positions": lambda i: i["category"] in REAL,
    "constructed (misses + adversarial)": lambda i: i["category"] not in REAL,
    "real, no mate theme": lambda i: i["category"] in REAL and not i["mate_theme"],
    "real, mate theme": lambda i: i["category"] in REAL and i["mate_theme"],
    "adversarial only": lambda i: i["category"] == "adversarial",
}


def build(results):
    out = {}
    for det, module in DETECTORS.items():
        items = [i for i in results if i["detector"] == det]
        out[det] = {"version": module.VERSION, "n_items": len(items), "groups": {}, "by_category": {}, "failures": []}
        for g, pred in GROUPS.items():
            sub = [i for i in items if pred(i)]
            if sub:
                out[det]["groups"][g] = {m: metrics(sub, m) for m in ("static", "evidence")}
        out[det]["uncertain_rate"] = {m: [sum(1 for i in items if i[m] == "uncertain"), len(items)] for m in ("static", "evidence")}
        cats = defaultdict(list)
        for i in items:
            cats[i["category"]].append(i)
        for c, sub in sorted(cats.items()):
            out[det]["by_category"][c] = {m: [sum(1 for i in sub if i["label"] == i[m]), len(sub)] for m in ("static", "evidence")}
        for i in items:
            for m in ("static", "evidence"):
                if i["label"] != i[m]:
                    out[det]["failures"].append({"mode": m, "id": i["id"], "category": i["category"], "label": i["label"],
                                                 "predicted": i[m], "move": i["move_san"], "fen": i["fen"],
                                                 "mate_theme": i["mate_theme"], "evidence": [i["evidence_best_cp"], i["evidence_after_cp"]]})
    return out


def markdown(report, meta, notes):
    sha = meta["positions_sha256"][:16]
    L = [
        f"# real_play_v1: detector scores ({meta['date']})",
        "",
        (f"Set: frozen `real_play_v1` (sha256 of positions.jsonl `{sha}...`). Engine for the evidence runs: "
         f"{meta['engine']} at depth {meta['depth']} (the production fast-pass budget; the set's labels used depth 14 separately)."),
        "",
        ("**Scoring rule (fixed before any detector ran):** each item has a `label`, the outcome a correct detector gives *with* "
         "engine evidence. `static` is the detector with no evidence; `evidence` is the detector with the evidence above. Positive "
         "class = `missed`. Every figure is `successes/denominator` with a 95% Wilson interval. Nothing was tuned on this set."),
        "",
    ]
    for det, d in report.items():
        L += [f"## {det} v{d['version']} ({d['n_items']} items)", "", "### Precision and recall for `missed`", "",
              "| Group | Mode | Precision (TP / predicted missed) | Recall (TP / labelled missed) | Exact agreement |", "|---|---|---|---|---|"]
        for g, modes in d["groups"].items():
            for m in ("static", "evidence"):
                x = modes[m]
                L.append(f"| {g} | {m} | {frac(*x['precision'])} | {frac(*x['recall'])} | {frac(*x['exact_agreement'])} |")
        L += ["", "### Exact agreement by item category", "", "| Category | Static | With evidence |", "|---|---|---|"]
        for c, x in d["by_category"].items():
            L.append(f"| {c} | {frac(*x['static'])} | {frac(*x['evidence'])} |")
        L += ["", "### Confusion matrix, all items (label -> predicted: count)", ""]
        for m in ("static", "evidence"):
            conf = d["groups"]["all items"][m]["confusion"]
            L.append(f"- **{m}:** " + ", ".join(f"{k}: {v}" for k, v in conf.items()))
        u = d["uncertain_rate"]
        L.append(f"- **uncertain rate (predicted `uncertain`):** static {frac(*u['static'])}; with evidence {frac(*u['evidence'])}"
                 " (the spec's E3 asks for this to be reported)")
        L += ["", f"### Every disagreement ({len(d['failures'])} item-mode pairs)", "",
              "| Mode | Item | Category | Label | Predicted | Move | Mate theme | Evidence (best, after cp) |", "|---|---|---|---|---|---|---|---|"]
        for f in d["failures"]:
            L.append(f"| {f['mode']} | {f['id']} | {f['category']} | {f['label']} | {f['predicted']} | {f['move']} | {f['mate_theme']} | {f['evidence'][0]}, {f['evidence'][1]} |")
        L.append("")
    if notes:
        L += ["## Reading these numbers", "", notes]
    return "\n".join(L) + "\n"


def main():
    import hashlib

    rows = [json.loads(line) for line in (SET / "positions.jsonl").read_text().splitlines() if line.strip()]
    with Engine() as engine:
        results = run(rows, engine)
        engine_name = engine.name
    today = date.today().isoformat()  # noqa: DTZ011 (the report is dated with the machine's local day)
    meta = {"date": today, "engine": engine_name, "depth": BATCH_BUDGET.depth,
            "positions_sha256": hashlib.sha256((SET / "positions.jsonl").read_bytes()).hexdigest(),
            "detector_versions": {k: v.VERSION for k, v in DETECTORS.items()}}
    report = build(results)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"real_play_v1_{today}.json").write_text(json.dumps({"meta": meta, "report": report, "items": results}, indent=1) + "\n")
    notes_path = REPORTS / f"real_play_v1_{today}_notes.md"
    (REPORTS / f"real_play_v1_{today}.md").write_text(markdown(report, meta, notes_path.read_text() if notes_path.exists() else ""))
    for det, d in report.items():
        for m in ("static", "evidence"):
            x = d["groups"]["all items"][m]
            print(f"{det} v{d['version']} {m:8} precision {frac(*x['precision'])} | recall {frac(*x['recall'])}")


if __name__ == "__main__":
    main()
