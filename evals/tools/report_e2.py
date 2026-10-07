"""Turn an E2 run (evals/runs/e2_<time>/results.json) into the published report under evals/reports/.

  cd backend && uv run python ../evals/tools/report_e2.py ../evals/runs/e2_<time>/results.json

The report restates the limits from docs/decisions/0003-e2-eval-design.md; read them before quoting a number.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = [("raw", "raw (no tools, no evidence)"), ("grounded", "grounded (first draft, no verifier)"),
           ("verified", "verified (what the player sees)")]


def pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def interval(s):
    return "n/a" if not s["ci95"] else f"{s['ci95'][0]:.0%} to {s['ci95'][1]:.0%}"


def by_kind(results, cfg, kind):
    total = correct = 0
    for r in results:
        if r["kind"] != kind:
            continue
        total += len(r["claims"][cfg])
        correct += sum(c["correct"] for c in r["claims"][cfg])
    return correct, total


def main(path):
    data = json.loads(Path(path).read_text())
    meta, summary, results = data["meta"], data["summary"], data["results"]
    n = meta["items"]
    lines = [
        f"# E2 explanation correctness, e2_v1 ({time_stamp(path)})", "",
        (f"{n} positions, model `{meta['model']}`, prompts {meta['prompts']}, verifier v{meta['verifier']}, scored at "
         f"Stockfish depth {meta['score_budget']['depth']}. Cost of the run: about ${meta['usd']} "
         f"({meta['tokens']['input']} input and {meta['tokens']['output']} output tokens). "
         "Design and limits: `docs/decisions/0003-e2-eval-design.md`."), "",
        "## Results", "",
        "| Config | Checkable claims | Correct | Correct rate (95% interval) | Texts with a wrong claim | Unverifiable statements | Empty texts | Not scored (extraction failed) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cfg, name in CONFIGS:
        s = summary[cfg]
        lines.append(f"| {name} | {s['claims_checked']} | {s['claims_correct']} | {pct(s['correct_rate'])} ({interval(s)}) | "
                     f"{s['texts_with_an_incorrect_claim']} of {s['texts']} | {s['unverifiable_statements']} | {s['empty_texts']} | "
                     f"{s.get('texts_not_scored_extraction_failed', 0)} |")
    st = summary["verified_statuses"]
    failed = sum(summary[c].get("texts_not_scored_extraction_failed", 0) for c, _ in CONFIGS)
    if failed:
        lines += ["", (f"**Scoring coverage: {failed} text(s) could not be scored because claim extraction failed twice. "
                       "They are NOT counted as correct; the rates above are over the texts that were scored.**")]
    mix = ", ".join(f"{k} {v}" for k, v in sorted(st.items()))
    lines += ["", (f"What the `verified` config returned: {mix} (out of {n}). "
                   "`fallback` and `unavailable` mean the text is the plain checked-facts text, not a model explanation."), "",
              "## By kind of move (correct / checked)", "", "| Config | good moves | bad moves |", "|---|---|---|"]
    for cfg, name in CONFIGS:
        g, b = by_kind(results, cfg, "good"), by_kind(results, cfg, "bad")
        lines.append(f"| {name} | {g[0]}/{g[1]} | {b[0]}/{b[1]} |")
    wrong = [(r["id"], cfg, c) for r in results for cfg in ("raw", "grounded", "verified")
             for c in r["claims"][cfg] if not c["correct"]]
    lines += ["", "## Wrong claims", ""]
    if not wrong:
        lines.append("None.")
    for rid, cfg, c in wrong[:30]:
        lines.append(f"- `{rid}` {cfg}: `{json.dumps(c['claim'])}`: {c['reason']}")
    if len(wrong) > 30:
        lines.append(f"- ... and {len(wrong) - 30} more in the run file")
    lines += ["", "## How to read this", ""]
    lines += [
        ("- The target in the spec is at least 98% correct checkable claims for `verified`. The scorer reuses the verifier's "
         "claim checks, so `verified` is partly graded by the logic that gates it; its rate says little on its own. The "
         "informative comparisons are `raw` against `grounded` (what evidence buys), `grounded` against `verified` (what the "
         "gate catches and costs), and how many statements stay unverifiable."),
        ("- Claims were extracted from the texts by a model (the same one that wrote them) and not hand-checked; extraction "
         "errors are unmeasured. 50 puzzle-derived positions, one run; intervals are wide and a re-run will differ."),
        "- No human has reviewed the items or a sample of the texts.",
    ]
    out = ROOT / "evals" / "reports" / f"e2_v1_{time_stamp(path)}.md"
    out.write_text("\n".join(lines) + "\n")
    print(out)


def time_stamp(path):
    stem = Path(path).parent.name  # e2_20261007_220000
    d = stem.split("_")[1]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


if __name__ == "__main__":
    main(sys.argv[1])
