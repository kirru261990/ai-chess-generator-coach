"""Run the E2 eval (spec section 07, T20): explanation correctness for three configurations.

  raw       the coach model with no tools and no evidence: it gets the position and the move and must explain
  grounded  the coach's FIRST draft written from the engine/detector evidence pack, with no verification
  verified  the full harness: draft, verify, one repair, then verified facts only (what a player would see)

grounded and verified share the same first draft, so the only difference between them is the verifier.

Scoring: an independent extraction prompt (prompts/extract_v1.md, a transcriber that must not correct the text) turns each
text into atomic claims; each claim is checked at SCORE_BUDGET (deeper than the verifier's budget) by the same claim
checks the verifier uses. Statements the extractor cannot express are counted as `unverifiable`, never as correct.
Independence limits are in docs/decisions/0003-e2-eval-design.md. Nothing here may be changed after the set is frozen.

Run from the repo root:
  cd backend && uv run python ../evals/tools/run_e2.py pilot              # evals/runs/e2_pilot set, throwaway
  cd backend && uv run python ../evals/tools/run_e2.py run [e2_v1|e2_v2] [N]  # a frozen set (default e2_v1)
  cd backend && uv run python ../evals/tools/run_e2.py rescore RESULTS.json    # re-extract and re-score saved texts
                                                                              # with the current extractor (no new texts)
"""

import json
import math
import sys
import time
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.coach import agent, verifier
from app.coach.llm import AnthropicDrafter, CoachUnavailable
from app.engine.stockfish import Budget, Engine

PROMPTS = Path(__file__).parent / "prompts"
EXTRACT_VERSION = "extract_v2"  # extract_v1 produced the e2_v1 numbers; it stays on disk, frozen
EXTRACT_PROMPT = (PROMPTS / f"{EXTRACT_VERSION}.md").read_text()
RAW_PROMPT = (PROMPTS / "raw_v1.md").read_text()
SCORE_BUDGET = Budget(depth=18)
CONFIGS = ("raw", "grounded", "verified")
MAX_USD = 5.0  # the run aborts if it would cost more than this
PRICE_PER_MTOK = {"input": 2.0, "output": 10.0}  # claude-sonnet-5-5 list price at the time of writing, USD


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def parse_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON")
    return json.loads(text[start:end + 1])


class Tally:
    def __init__(self):
        self.tokens = {"input": 0, "output": 0}

    def add(self, draft):
        self.tokens["input"] += draft.input_tokens
        self.tokens["output"] += draft.output_tokens

    def usd(self):
        return sum(self.tokens[k] * PRICE_PER_MTOK[k] / 1e6 for k in self.tokens)


def raw_text(drafter, item, board, tally):
    msg = (f"Position (FEN): {item['fen']}\nThe player has the {item['user_color']} pieces and played "
           f"{item['move_san']}.\nExplain why this move was good or bad.")
    draft = drafter.draft(RAW_PROMPT, [{"role": "user", "content": msg}])
    tally.add(draft)
    return draft.text.strip()


def extract_claims(drafter, item, text, tally):
    """(claims, unverifiable, error). The extractor sees only the position, the move and the text."""
    if not text:
        return [], [], None
    msg = (f"FEN: {item['fen']}\nPlayer: {item['user_color']}\nPlayed move: {item['move_san']}\n\n"
           f"<explanation>\n{text}\n</explanation>")
    for _ in range(2):
        draft = drafter.draft(EXTRACT_PROMPT, [{"role": "user", "content": msg}])
        tally.add(draft)
        try:
            data = parse_json(draft.text)
            claims, unv = data.get("claims", []), data.get("unverifiable", [])
            if isinstance(claims, list) and isinstance(unv, list):
                return claims, [str(u) for u in unv], None
        except ValueError:
            pass
    return [], [], "extraction failed"


def score_claims(engine, item, claims):
    """Check each claim at the scoring budget. Returns per-claim results."""
    ctx = verifier.Context(item["fen"], chess.WHITE if item["user_color"] == "white" else chess.BLACK, item["move_uci"])
    v = verifier.Verifier(engine, ctx, SCORE_BUDGET)
    out = []
    for c in claims:
        if not isinstance(c, dict):
            out.append({"claim": c, "correct": False, "reason": "not an object"})
            continue
        try:
            v.check(c)
            out.append({"claim": c, "correct": True})
        except (ValueError, TypeError, AttributeError, KeyError, chess.InvalidMoveError, chess.IllegalMoveError,
                chess.AmbiguousMoveError) as e:
            out.append({"claim": c, "correct": False, "reason": str(e)})
    return out


def run_item(engine, drafter, item, tally):
    board = chess.Board(item["fen"])
    user = chess.WHITE if item["user_color"] == "white" else chess.BLACK
    res = {"id": item["id"], "kind": item["kind"], "texts": {}, "claims": {}, "unverifiable": {}, "notes": {}}
    res["texts"]["raw"] = raw_text(drafter, item, board, tally)
    out = agent.explain_move(engine, drafter, item["fen"], user, item["move_uci"], keep_drafts=True)
    for a in out["attempts"]:
        if a.get("tokens"):
            tally.tokens["input"] += a["tokens"]["input"]
            tally.tokens["output"] += a["tokens"]["output"]
    first = out["attempts"][0] if out["attempts"] else {}
    grounded = first.get("draft", "")
    if not grounded and first.get("raw_reply"):  # an unreadable first draft is still what the model wrote: score it
        grounded = first["raw_reply"].strip()
    res["texts"]["grounded"] = grounded
    res["notes"]["grounded_draft_status"] = first.get("draft_status", "no draft")
    res["texts"]["verified"] = out["text"]
    res["notes"]["verified_status"] = out["status"]
    res["notes"]["grounded_first_draft_ok"] = first.get("ok")
    for cfg in CONFIGS:
        claims, unv, err = extract_claims(drafter, item, res["texts"][cfg], tally)
        res["claims"][cfg] = score_claims(engine, item, claims)
        res["unverifiable"][cfg] = unv
        res["scored"] = {**res.get("scored", {}), cfg: bool(res["texts"][cfg]) and not err}
        if err:
            res["notes"][f"{cfg}_extraction"] = err
    return res


def summarise(results):
    summary = {}
    for cfg in CONFIGS:
        total = correct = unv = texts = texts_bad = empty = unscored = 0
        for r in results:
            cl = r["claims"][cfg]
            texts += 1
            empty += not r["texts"][cfg]
            unscored += bool(r["texts"][cfg]) and not r.get("scored", {}).get(cfg, True)  # extraction failed
            total += len(cl)
            good = sum(c["correct"] for c in cl)
            correct += good
            unv += len(r["unverifiable"][cfg])
            texts_bad += good < len(cl)
        lo_hi = wilson(correct, total)
        summary[cfg] = {"texts": texts, "empty_texts": empty, "claims_checked": total, "claims_correct": correct,
                        "correct_rate": correct / total if total else None,
                        "ci95": list(lo_hi) if lo_hi else None, "unverifiable_statements": unv,
                        "texts_with_an_incorrect_claim": texts_bad,
                        "texts_not_scored_extraction_failed": unscored}
    statuses = {}
    for r in results:
        s = r["notes"]["verified_status"]
        statuses[s] = statuses.get(s, 0) + 1
    summary["verified_statuses"] = statuses
    return summary


def rescore(path):
    """Re-extract and re-score the saved texts of an earlier run with the current extraction prompt. Separates the effect of
    a changed extractor from a changed coach: the texts are identical, only the measuring instrument differs."""
    data = json.loads(Path(path).read_text())
    set_dir = ROOT / data["meta"]["set"]
    items = {json.loads(line)["id"]: json.loads(line) for line in (set_dir / "positions.jsonl").read_text().splitlines() if line}
    drafter, tally = AnthropicDrafter(), Tally()
    results = []
    with Engine() as engine:
        for old in data["results"]:
            item = items[old["id"]]
            res = {**old, "claims": {}, "unverifiable": {}, "scored": {}}
            for cfg in CONFIGS:
                claims, unv, err = extract_claims(drafter, item, old["texts"][cfg], tally)
                res["claims"][cfg] = score_claims(engine, item, claims)
                res["unverifiable"][cfg] = unv
                res["scored"][cfg] = bool(old["texts"][cfg]) and not err
            results.append(res)
            print(f"  {old['id']} rescored  (${tally.usd():.2f} so far)", flush=True)
    meta = {**data["meta"], "rescored_with": EXTRACT_VERSION, "rescore_usd": round(tally.usd(), 2)}
    summary = summarise(results)
    out = Path(path).with_name("rescored_" + EXTRACT_VERSION + ".json")
    out.write_text(json.dumps({"meta": meta, "summary": summary, "results": results}, indent=1))
    print(json.dumps(summary, indent=1))
    print(f"\nrescored results: {out}")


def main(argv):
    if argv and argv[0] == "rescore":
        return rescore(argv[1])
    if not argv or argv[0] not in ("pilot", "run"):
        sys.exit(__doc__)
    pilot = argv[0] == "pilot"
    set_name = argv[1] if len(argv) > 1 and argv[1].startswith("e2_v") else "e2_v1"
    set_dir = ROOT / "evals" / ("runs/e2_pilot" if pilot else f"sets/{set_name}")
    items = [json.loads(line) for line in (set_dir / "positions.jsonl").read_text().splitlines() if line.strip()]
    nums = [a for a in argv[1:] if a.isdigit()]
    limit = int(nums[0]) if nums else None
    items = items[:limit] if limit else items
    drafter = AnthropicDrafter()
    tally = Tally()
    tag = "pilot_" if pilot else ("" if set_name == "e2_v1" else f"{set_name[3:]}_")
    out_dir = ROOT / "evals" / "runs" / f"e2_{tag}{time.strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True)
    results = []
    with Engine() as engine:
        for item in items:
            try:
                results.append(run_item(engine, drafter, item, tally))
            except CoachUnavailable as e:
                sys.exit(f"the coach model is unavailable: {e}")
            print(f"  {item['id']} done  (${tally.usd():.2f} so far)", flush=True)
            if tally.usd() > MAX_USD:
                sys.exit(f"stopped: cost passed the ${MAX_USD:.0f} limit")
    summary = summarise(results)
    meta = {"set": str(set_dir.relative_to(ROOT)), "items": len(items), "model": drafter.model,
            "prompts": {"why": agent.PROMPT_VERSION, "extract": EXTRACT_VERSION, "raw": "raw_v1"},
            "verifier": verifier.VERSION, "score_budget": {"depth": SCORE_BUDGET.depth},
            "tokens": tally.tokens, "usd": round(tally.usd(), 2)}
    (out_dir / "results.json").write_text(json.dumps({"meta": meta, "summary": summary, "results": results}, indent=1))
    print(json.dumps({"meta": meta, "summary": summary}, indent=1))
    print(f"\nfull results: {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1:])
