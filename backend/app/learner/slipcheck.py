"""Hand-check page for the first-slip drills (ADR 0020): 30 of the owner's own drills, one per game.

  uv run python -m app.learner.slipcheck make                 # data/drills/slipcheck_v1.html (sample frozen on first run)
  uv run python -m app.learner.slipcheck score ANSWERS.txt    # gate: 27 of 30 real (90%, as the earlier checks)

One question per position, asked on the board before the move: "Is the move you played a real mistake, and are the green moves clearly
better?" Only the board, the side, the played move and the accepted moves are shown: no score and no loss. The page is a fragment (the
Artifact tool wraps it). The sample is chosen by a hash of the drill id, so it does not depend on the order of the bank.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path

import chess
import chess.svg

from app.detectors import prd_rules as R
from app.learner import drillbank, drillcheck, handcheck, slipround
from app.learner.explorer import board_svg, plain, side

VERSION = 1
N = 30
GATE = 27
ID_PREFIX = "sc"


def key_path() -> Path:
    return drillbank.bank_dir() / f"slipcheck_v{VERSION}_key.json"


def page_path() -> Path:
    return drillbank.bank_dir() / f"slipcheck_v{VERSION}.html"


def _order(drill: dict) -> str:
    return hashlib.sha256(f"slipcheck-v{VERSION}|{drill['id']}".encode()).hexdigest()


def sample(drills: list[dict], n: int = N) -> list[dict]:
    """`n` own drills by hash order, never two from one game. Public-game drills are not part of this check."""
    out, used = [], set()
    for d in sorted((d for d in drills if d["source"] == "own"), key=_order):
        if d["game_id"] not in used:
            used.add(d["game_id"])
            out.append(d)
        if len(out) == n:
            break
    return out


POINTS = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
LINE_PLIES = 4  # the move and up to three more: far enough to see a trade settle, short enough to check by eye


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(POINTS.get(p.piece_type, 0) * (1 if p.color == color else -1) for p in board.piece_map().values())


def _pawns(cp: int) -> str:
    n = round(abs(cp) / 100, 1)
    n = int(n) if n == int(n) else n
    return f"{n} pawn" if n == 1 else f"{n} pawns"


def _points(n: int) -> str:
    return f"{n} point" if n == 1 else f"{n} points"


def _line_text(board: chess.Board, move: chess.Move, analyser) -> str:
    """The expected line after `move`, in plain words, and what it does to material and the score, all from engine facts."""
    me = board.turn
    after = board.copy(stack=False)
    after.push(move)
    ucis = [move.uci()]
    outcome = ""
    if not after.is_game_over():
        line = analyser.analyse(after).best
        ucis += list(line.pv)[: LINE_PLIES - 1]
        score = R.line_score(line, me)
        end = board.copy(stack=False)
        for u in ucis:
            end.push(chess.Move.from_uci(u))
        delta = _material(end, me) - _material(board, me)
        if line.mate is not None:
            outcome = "That line ends in checkmate " + ("for you." if score > 0 else "against you.")
        else:
            if delta < 0:
                material = f"You end up {_points(-delta)} behind."
            elif delta > 0:
                material = f"You end up {_points(delta)} ahead."
            else:
                material = "Material stays level." if score >= 0 or abs(score) < 50 else "In these moves no material is lost, but the position gets worse."
            if abs(score) < 50:
                rating = "The computer rates the position as roughly equal."
            else:
                rating = f"The computer rates you about {_pawns(score)} {'ahead' if score > 0 else 'behind'}."
            outcome = f"{material} {rating}"
    else:
        outcome = "That ends the game."
    return f"After {plain(board, move.uci())}, the computer expects: {handcheck.line_words(board, ucis, me)}. {outcome}"


def explain(d: dict, analyser) -> dict[str, str]:
    """Why the computer prefers the accepted move, in plain words. Every sentence comes from an engine line (the same pinned engine
    that chose the drill) and a material count; no language model is involved (AGENTS.md rules 1 and 2)."""
    board = chess.Board(d["fen"])
    out = {"played": _line_text(board, chess.Move.from_uci(d["played"]), analyser), "better": ""}
    if d.get("evidence"):
        out["played"] += f" Compared with the better move, your move gives up about {_pawns(d['evidence']['loss_cp'])}."
    if d["accepted"]:
        out["better"] = _line_text(board, chess.Move.from_uci(d["accepted"][0]), analyser)
    return out


def render_card(item_id: str, d: dict, why: dict[str, str] | None = None) -> str:
    board = chess.Board(d["fen"])
    me = board.turn
    played = chess.Move.from_uci(d["played"])
    arrows = [chess.svg.Arrow(played.from_square, played.to_square, color=handcheck.RED)]
    arrows += [chess.svg.Arrow(m.from_square, m.to_square, color=handcheck.GREEN)
               for m in (chess.Move.from_uci(u) for u in d["accepted"])]
    better = ", ".join(f"<b>{html.escape(plain(board, u))}</b>" for u in d["accepted"])
    setup = f"You are <b>{side(me)}</b>. You played <b>{html.escape(plain(board, d['played']))}</b> <i class=\"r\">(red)</i>."
    ask = (f"Is that a real mistake? The computer prefers {better} <i class=\"g\">(green)</i>. "
           "Is a green move clearly better, and could you have seen why?")
    more = ""
    if why:
        more = (f'<details><summary>Why the computer prefers it</summary><p><b>Your move.</b> {html.escape(why["played"])}</p>'
                f'<p><b>The better move.</b> {html.escape(why["better"])}</p>'
                '<p class="pts">Computer lines are from the same engine that found this slip. Points: pawn 1, knight or bishop 3, rook 5, queen 9.</p></details>'
                if why["better"] else "")
    return (f'<section class="card" id="{item_id}" data-qs="A" hidden><div class="q" data-qid="A" hidden>'
            f'<figure>{board_svg(board, me, arrows, {})}</figure><p class="setup">{setup}</p><p class="ask">{ask}</p>{more}'
            f'<div class="btns" data-item="{item_id}" data-q="A">'
            '<button data-v="yes" class="yes">Yes<kbd>Y</kbd></button><button data-v="no" class="no">No<kbd>N</kbd></button>'
            '<button data-v="cant" class="cant">Can\'t tell<kbd>C</kbd></button></div></div></section>')


# The page is the drill check's page with its count and wording changed, so the two checks look and behave the same.
PAGE = (drillcheck.PAGE.replace("repeat(20,1fr)", f"repeat({N},1fr)").replace("<title>Drill Check</title>", "<title>Slip Check</title>")
        .replace("Is it a real mistake?", "Is it a real slip?")
        .replace("20 moves from other players' games (public Lichess games).", f"{N} moves from your own games."))


def _analyser():
    """The pinned evidence engine over the slip cache (the one that built the drills), so a line seen before is read, not re-searched."""
    from app.db.schema import connect
    from app.engine.evidence import open_evidence
    from app.learner import slipbank

    return open_evidence(connect(str(slipbank.cache_path())))


def make(bank: Path | None = None, analyser=None) -> Path:
    drills = [json.loads(line) for line in bank.open()] if bank else slipround.read_slips()
    by_id = {d["id"]: d for d in drills}
    if key_path().exists():
        key = json.loads(key_path().read_text())
    else:
        chosen = sample(drills)
        if len(chosen) < N:
            raise ValueError(f"only {len(chosen)} own first-slip drills from separate games; the check needs {N}")
        key = {"version": VERSION, "gate": GATE, "items": [
            {"id": f"{ID_PREFIX}-{n:02d}", "drill_id": d["id"], "game_id": d["game_id"], "avg_rating": d["avg_rating"],
             "versions": d["versions"], "questions": ["A"]} for n, d in enumerate(chosen, 1)]}
    chosen = [by_id[i["drill_id"]] for i in key["items"]]
    if any("why" not in i for i in key["items"]):  # the sample stays as it was; the explanation is added once and then frozen too
        with (nullcontext(analyser) if analyser else _analyser()) as engine:
            for it, d in zip(key["items"], chosen, strict=True):
                it.setdefault("why", explain(d, engine))
    key_path().write_text(json.dumps(key, indent=1) + "\n")
    cards = "\n".join(render_card(it["id"], d, it["why"]) for it, d in zip(key["items"], chosen, strict=True))
    page_path().write_text(PAGE.replace("__CARDS__", cards).replace("__TOTAL__", str(len(chosen))).replace("__KEY__", f"slipcheck_v{VERSION}"))
    return page_path()


def parse_answers(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(rf"^({ID_PREFIX}-\d+):\s*(.+)$", text, re.MULTILINE):
        out[m.group(1)] = dict(re.findall(r"\b(A)\s+(yes|no|cant|-)\b", m.group(2)))
    return out


def score(answers_text: str) -> dict:
    key = json.loads(key_path().read_text())
    answers = parse_answers(answers_text)
    items, unanswered = [], []
    for it in key["items"]:
        a = answers.get(it["id"], {})
        if a.get("A") in (None, "-"):
            unanswered.append(it["id"])
        items.append({"id": it["id"], "avg_rating": it["avg_rating"], "answers": a, "real": a.get("A") == "yes"})
    real = sum(i["real"] for i in items)
    result = {"version": VERSION, "scored_at": datetime.now(UTC).isoformat(timespec="seconds"), "real": real, "of": len(items),
              "gate": GATE, "passed": real >= GATE and not unanswered, "unanswered": unanswered,
              "not_real": [i for i in items if not i["real"]], "items": items}
    key_path().with_name(f"slipcheck_v{VERSION}_result.json").write_text(json.dumps(result, indent=1) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["make"]:
        print(make())
    elif argv[:1] == ["score"] and len(argv) == 2:
        print(json.dumps(score(Path(argv[1]).read_text()), indent=1))
    else:
        print("usage: slipcheck make | score ANSWERS.txt", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
