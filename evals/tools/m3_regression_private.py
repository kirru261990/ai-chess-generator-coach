"""Private M3 regression set from the owner's first hand-check (ADR 0011, "Why the 16 were not real"). Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/m3_regression_private.py build|run [--data DIR]

The 30 positions are the owner's own games, so the set lives in `data/evidence/missed_threat_v3_private/` (git-ignored; the repo is
public). It is a REGRESSION check, not a score: ADR 0011's reading of the 30 produced the v2 rule (ADR 0013), so they cannot measure it
(the ADR forbids tuning on them and scoring again). The real test is a new sample.

Labels, fixed here before v2 is run on this set. They come only from the owner's answers (the `real` flag in the result file) and the
reasons in ADR 0011 (decisions are by hc id):
- `missed`: the 14 the owner called real; hc3-06, 07, 12, 13, 18 (the threat was real, the page wording failed); hc3-27 (discovered
  attack, a real miss the owner had not seen).
- `not_missed`: hc3-02, 03, 08, 11, 15, 26 (the move lost for another reason: the forced-threat loss is zero or negative).
- excluded: hc3-05 (a counter-attack answers it), hc3-20, 21, 28 (the threat costs, the owner saw none, reason not recorded).
`known_disagreement`: hc3-29 (called real, but executing the threat backfires: v2 is expected to abstain; ADR 0013 case 4).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

REWORDED = {"hc3-06", "hc3-07", "hc3-12", "hc3-13", "hc3-18", "hc3-27"}
DEFECT = {"hc3-02", "hc3-03", "hc3-08", "hc3-11", "hc3-15", "hc3-26"}
EXCLUDED = {"hc3-05", "hc3-20", "hc3-21", "hc3-28"}
KNOWN = {"hc3-29"}


def build(data: Path):
    sample = json.loads((data / "evidence" / "handcheck_m3_v1.json").read_text())
    result = json.loads((data / "evidence" / "handcheck_m3_v1_result.json").read_text())
    real = {i["id"]: i["real"] for i in result["items"]}
    rows = []
    for it in sample["items"]:
        i = it["id"]
        if i in EXCLUDED:
            continue
        label = "not_missed" if i in DEFECT else "missed" if (real[i] or i in REWORDED) else None
        if label is None:
            raise SystemExit(f"{i} has no label: not real, not in any list")
        f = it["flag"]
        rows.append({"id": i, "label": label, "fen": f["fen"], "move_uci": f["move"], "ply": f["ply"],
                     "known_disagreement": i in KNOWN, "owner_real": real[i]})
    out = data / "evidence" / "missed_threat_v3_private"
    out.mkdir(exist_ok=True)
    (out / "positions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{len(rows)} items: {dict(Counter(r['label'] for r in rows))}, excluded {sorted(EXCLUDED)} -> {out}")


def run(data: Path):
    from app.db.schema import connect
    from app.detectors import missed_threat
    from app.engine.evidence import open_evidence

    rows = [json.loads(x) for x in (data / "evidence" / "missed_threat_v3_private" / "positions.jsonl").read_text().splitlines()]
    conn = connect(str(data / "evidence" / "missed_threat_v3_private" / "cache.sqlite3"))
    table, tp, fp, fn = [], 0, 0, 0
    with open_evidence(conn) as analyser:
        for r in rows:
            f = missed_threat.detect(chess.Board(r["fen"]), chess.Move.from_uci(r["move_uci"]), r["ply"], analyser)
            pred = f.outcome == "missed"
            tp += pred and r["label"] == "missed"
            fp += pred and r["label"] != "missed"
            fn += (not pred) and r["label"] == "missed"
            table.append((r["id"], r["label"], f"{f.outcome}/{f.reason}", "known" if r["known_disagreement"] else ""))
    for t in table:
        print("  ".join(str(x) for x in t))
    print(f"missed_threat v{missed_threat.VERSION}: flagged-and-labelled-missed {tp}, flagged-but-not-missed {fp}, "
          f"labelled-missed-but-not-flagged {fn} (regression only, not a score)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "run"])
    ap.add_argument("--data", default=str(Path.home() / "Projects" / "ai-chess-generator-coach" / "data"))
    a = ap.parse_args()
    (build if a.mode == "build" else run)(Path(a.data))
