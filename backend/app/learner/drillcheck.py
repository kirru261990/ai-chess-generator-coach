"""Hand-check page for the drill bank (ADR 0017 decision 9): 20 drills, one per game, 10 hanging-own-piece and 10 missed-free-piece.

  uv run python -m app.learner.drillcheck make                 # data/drills/drillcheck_v1.html (sample frozen on first run)
  uv run python -m app.learner.drillcheck score ANSWERS.txt    # gate: 18 of 20 real (90%, as the 27 of 30 of the earlier checks)

Same questions and page as `handcheck` (A: is the loss real; B, for hanging pieces: could it have been kept safe), applied to
Lichess drills. The sample is chosen by a hash of the drill id, so it does not depend on what the bank holds in what order.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.learner import drillbank, handcheck

VERSION = 1
PER_TYPE = 10
GATE = 18
ID_PREFIX = "dc"


def key_path() -> Path:
    return drillbank.bank_dir() / f"drillcheck_v{VERSION}_key.json"


def page_path() -> Path:
    return drillbank.bank_dir() / f"drillcheck_v{VERSION}.html"


def _order(drill: dict) -> str:
    return hashlib.sha256(f"drillcheck-v{VERSION}|{drill['id']}".encode()).hexdigest()


def sample(drills: list[dict], per_type: int = PER_TYPE) -> list[dict]:
    """`per_type` drills of each type, by hash order, never two from one game (and never an experimental drill)."""
    out: list[dict] = []
    used: set[str] = set()
    for t in ("M1", "M2"):
        taken = 0
        for d in sorted((d for d in drills if d["type"] == t and not d["experimental"]), key=_order):
            if taken >= per_type:
                break
            if d["game_id"] in used:
                continue
            used.add(d["game_id"])
            out.append(d)
            taken += 1
    return out


def questions(d: dict) -> list[str]:
    return ["A", "B"] if d["type"] == "M1" else ["A"]


def make(bank: Path | None = None) -> Path:
    bank = bank or drillbank.bank_path()
    drills = [json.loads(line) for line in bank.open()]
    if key_path().exists():
        key = json.loads(key_path().read_text())
        by_id = {d["id"]: d for d in drills}
        chosen = [by_id[i["drill_id"]] for i in key["items"]]
    else:
        chosen = sample(drills)
        items = [{"id": f"{ID_PREFIX}-{n:02d}", "drill_id": d["id"], "type": d["type"], "game_id": d["game_id"],
                  "avg_rating": d["avg_rating"], "questions": questions(d)} for n, d in enumerate(chosen, 1)]
        key_path().write_text(json.dumps({"version": VERSION, "gate": GATE, "items": items}, indent=1) + "\n")
    key = json.loads(key_path().read_text())
    cards = "\n".join(
        handcheck.card({"id": it["id"], "type": it["type"]}, d["evidence"], d["alternatives"])
        for it, d in zip(key["items"], chosen, strict=True))
    page = (handcheck.PAGE.replace("__CARDS__", cards).replace("__TOTAL__", str(len(chosen)))
            .replace("__KEY__", f"drillcheck_v{VERSION}"))
    for old, new in PAGE_TEXT:
        if old not in page:
            raise RuntimeError(f"the handcheck page text changed: {old[:40]!r}")
        page = page.replace(old, new)
    page_path().write_text(page)
    return page_path()


PAGE_TEXT = (
    ("These are 30 moves from your own games that the mistake finder flagged.",
     ("These are 20 moves from other players' games (public Lichess games, ratings 500 to 1800) that the mistake finder flagged. "
      "You were not in these games: \"you\" means the player who moved.")),
    ("<title>Mistake Check</title>", "<title>Drill Check</title>"),
    (("<p class=\"note\">This is version 2. Version 1 counted a trade (you take, they take back) as a hanging piece; you spotted that,\n"
      "and those positions are gone.</p>\n"), ""),
    ("<p class=\"note\">None of these positions will appear in your future tests: they all come from the practice pool.</p>\n", ""),
    ("my_mistake_check.txt", "my_drill_check.txt"),
)


def parse_answers(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(rf"^({ID_PREFIX}-\d+):\s*(.+)$", text, re.MULTILINE):
        out[m.group(1)] = dict(re.findall(r"\b([AB])\s+(yes|no|cant|-)\b", m.group(2)))
    return out


def score(answers_text: str) -> dict:
    key = json.loads(key_path().read_text())
    answers = parse_answers(answers_text)
    items, unanswered = [], []
    for it in key["items"]:
        a = answers.get(it["id"], {})
        asked = ["A"] if a.get("A") != "yes" else it["questions"]  # B is only asked after a yes to A
        if not a.get("A") or any(a.get(q) in (None, "-") for q in asked):
            unanswered.append(it["id"])
        items.append({"id": it["id"], "type": it["type"], "avg_rating": it["avg_rating"], "answers": a,
                      "real": all(a.get(q) == "yes" for q in it["questions"])})
    real = sum(i["real"] for i in items)
    by_type = {t: {"real": sum(i["real"] for i in items if i["type"] == t), "of": sum(i["type"] == t for i in items)}
               for t in ("M1", "M2")}
    result = {"version": VERSION, "scored_at": datetime.now(UTC).isoformat(timespec="seconds"), "real": real, "of": len(items),
              "gate": GATE, "passed": real >= GATE and not unanswered, "by_type": by_type, "unanswered": unanswered,
              "not_real": [i for i in items if not i["real"]], "items": items}
    key_path().with_name(f"drillcheck_v{VERSION}_result.json").write_text(json.dumps(result, indent=1) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["make"]:
        print(make())
    elif argv[:1] == ["score"] and len(argv) == 2:
        print(json.dumps(score(Path(argv[1]).read_text()), indent=1))
    else:
        print("usage: drillcheck make | score ANSWERS.txt", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
