"""Score `missed_threat` (M3) on the frozen eval set missed_threat_v1. Reads the set; never edits it or the detector.

Run:  cd backend && uv run python ../evals/tools/score_missed_threat.py [--limit N]

The detector runs with the production evidence engine (pinned Stockfish, depth 18) into a scratch cache under evals/runs/,
never into data/coach.sqlite3. Detector outcomes map to the set's labels: missed -> missed, met -> met, uncertain -> uncertain,
no_threat and skipped -> not_applicable.

Output: evals/reports/missed_threat_v1_<date>.json (every item) and .md (tables; notes appended from ..._notes.md if present).
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_detectors import frac

from app.db.schema import connect
from app.detectors import missed_threat
from app.engine.evidence import open_evidence

SET = ROOT / "evals" / "sets" / "missed_threat_v1"
REPORTS = ROOT / "evals" / "reports"
RUNS = ROOT / "evals" / "runs"
MAP = {"missed": "missed", "met": "met", "uncertain": "uncertain", "no_threat": "not_applicable", "skipped": "not_applicable"}
TARGET_PRECISION, TARGET_RECALL = 0.90, 0.85  # TASKS M3c, fixed before the detector ran


def run(rows, analyser):
    out = []
    for r in rows:
        board = chess.Board(r["fen"])
        move = chess.Move.from_uci(r["move_uci"])
        previous = chess.Board(r["previous_fen"]) if r.get("previous_fen") else None
        f = missed_threat.detect(board, move, r["ply"], analyser, previous=previous)
        out.append({**{k: r[k] for k in ("id", "category", "label", "fen", "move_san", "ply", "band", "constructed")},
                    "outcome": f.outcome, "reason": f.reason, "predicted": MAP[f.outcome],
                    "threat_kind": (f.evidence or {}).get("threat_kind"), "eval_loss": (f.evidence or {}).get("eval_loss")})
    return out


def metrics(items):
    tp = sum(1 for i in items if i["label"] == "missed" and i["predicted"] == "missed")
    fp = sum(1 for i in items if i["label"] != "missed" and i["predicted"] == "missed")
    fn = sum(1 for i in items if i["label"] == "missed" and i["predicted"] != "missed")
    agree = sum(1 for i in items if i["label"] == i["predicted"])
    conf = Counter((i["label"], i["predicted"]) for i in items)
    return {"n": len(items), "tp": tp, "fp": fp, "fn": fn, "precision": [tp, tp + fp], "recall": [tp, tp + fn],
            "exact_agreement": [agree, len(items)], "confusion": {f"{a}->{b}": c for (a, b), c in sorted(conf.items())}}


GROUPS = {
    "all items": lambda i: True,
    "real positions (real_*)": lambda i: i["category"].endswith("_real") or i["category"] in ("constructed_quiet", "hung_not_threat", "quiet_blunder"),
    "constructed (constructed_missed + adversarial)": lambda i: i["constructed"],
    "adversarial only": lambda i: i["category"] == "adversarial",
}


def build(results):
    groups = {g: metrics([i for i in results if p(i)]) for g, p in GROUPS.items() if any(p(i) for i in results)}
    cats = defaultdict(list)
    for i in results:
        cats[i["category"]].append(i)
    by_cat = {c: [sum(1 for i in s if i["label"] == i["predicted"]), len(s)] for c, s in sorted(cats.items())}
    fails = [{k: i[k] for k in ("id", "category", "label", "predicted", "outcome", "reason", "move_san", "fen", "threat_kind", "eval_loss")}
             for i in results if i["label"] != i["predicted"]]
    reasons = Counter(f"{i['label']}->{i['outcome']}:{i['reason']}" for i in results if i["label"] != i["predicted"])
    uncertain = [sum(1 for i in results if i["predicted"] == "uncertain"), len(results)]
    return {"groups": groups, "by_category": by_cat, "failures": fails, "failure_reasons": dict(reasons.most_common()),
            "uncertain_rate": uncertain}


def markdown(report, meta, notes):
    g = report["groups"]["all items"]
    p_ok = g["precision"][1] and g["precision"][0] / g["precision"][1] >= TARGET_PRECISION
    r_ok = g["recall"][1] and g["recall"][0] / g["recall"][1] >= TARGET_RECALL
    L = [f"# missed_threat_v1: M3 detector scores ({meta['date']})", "",
         (f"Set: frozen `missed_threat_v1` (positions.jsonl sha256 `{meta['positions_sha256'][:16]}...`). Detector: `missed_threat` "
          f"v{meta['detector_version']} with {meta['engine']} at depth {meta['depth']} (labels used depth 14 separately). "
          f"Targets fixed before the run: precision >= {TARGET_PRECISION}, recall >= {TARGET_RECALL}. Positive class = `missed`. "
          "Every figure is `successes/denominator` with a 95% Wilson interval. Nothing was tuned on this set."), "",
         (f"**All items: precision {frac(*g['precision'])} ({'meets' if p_ok else 'misses'} the target as a point estimate); "
          f"recall {frac(*g['recall'])} ({'meets' if r_ok else 'misses'} the target as a point estimate).**"), "",
         "## Precision and recall for `missed`", "",
         "| Group | Precision (TP / predicted missed) | Recall (TP / labelled missed) | Exact agreement |", "|---|---|---|---|"]
    for name, x in report["groups"].items():
        L.append(f"| {name} | {frac(*x['precision'])} | {frac(*x['recall'])} | {frac(*x['exact_agreement'])} |")
    L += ["", "## Exact agreement by item category", "", "| Category | Agreement |", "|---|---|"]
    for c, x in report["by_category"].items():
        L.append(f"| {c} | {frac(*x)} |")
    L += ["", "## Confusion matrix, all items (label -> predicted: count)", "",
          ", ".join(f"{k}: {v}" for k, v in g["confusion"].items()), "",
          f"Predicted `uncertain` (the spec's E3 asks for this): {frac(*report['uncertain_rate'])}.", "",
          "## Disagreements by detector reason", ""]
    for k, v in report["failure_reasons"].items():
        L.append(f"- {k}: {v}")
    L += ["", f"## Every disagreement ({len(report['failures'])})", "",
          "| Item | Category | Label | Predicted | Detector outcome:reason | Move | Kind | Loss cp |", "|---|---|---|---|---|---|---|---|"]
    for f in report["failures"]:
        L.append(f"| {f['id']} | {f['category']} | {f['label']} | {f['predicted']} | {f['outcome']}:{f['reason']} | {f['move_san']} | "
                 f"{f['threat_kind'] or ''} | {f['eval_loss'] if f['eval_loss'] is not None else ''} |")
    if notes:
        L += ["", "## Reading these numbers", "", notes]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    rows = [json.loads(line) for line in (SET / "positions.jsonl").read_text().splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]
    RUNS.mkdir(exist_ok=True)
    conn = connect(str(RUNS / "missed_threat_v1_cache.sqlite3"))
    with open_evidence(conn) as analyser:
        results = run(rows, analyser)
        meta = {"date": date.today().isoformat(), "engine": analyser.config.version, "depth": analyser.config.depth,
                "engine_config_id": analyser.config.id, "detector_version": missed_threat.VERSION,
                "positions_sha256": hashlib.sha256((SET / "positions.jsonl").read_bytes()).hexdigest()}
    report = build(results)
    if args.limit:
        print(json.dumps(report["groups"]["all items"], indent=1))
        return
    REPORTS.mkdir(exist_ok=True)
    stem = f"missed_threat_v1_{meta['date']}"
    (REPORTS / f"{stem}.json").write_text(json.dumps({"meta": meta, "report": report, "items": results}, indent=1) + "\n")
    notes = REPORTS / f"{stem}_notes.md"
    (REPORTS / f"{stem}.md").write_text(markdown(report, meta, notes.read_text() if notes.exists() else ""))
    g = report["groups"]["all items"]
    print(f"missed_threat v{missed_threat.VERSION}: precision {frac(*g['precision'])} | recall {frac(*g['recall'])}")


if __name__ == "__main__":
    main()
