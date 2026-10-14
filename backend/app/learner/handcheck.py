"""Step 1c hand-check (PRD v2 §14 Step 1; ADR 0006): the owner judges 30 flagged positions. Gate: at least 27 are real.

  uv run python -m app.learner.handcheck make               # sample once, write data/evidence/handcheck_v1.html
  uv run python -m app.learner.handcheck score ANSWERS.txt  # score the owner's copied answers

Rules fixed before the owner answers (so the result cannot move the goalposts):
- **Sample:** PRACTICE-pool MISTAKE positions only (held-out positions must stay unseen, PRD §5.3), never one the owner has
  already seen (no row of the same board marked, `seen.py`), at most one per (game, ply): 8 M1 "moved into danger", 7 M1 "left behind", 15 M2, in
  a fixed pseudo-random order. The sample is frozen in `data/evidence/handcheck_v1.json` the first time; `make` afterwards only
  rebuilds the page from it. The sampled positions and their sibling rows are marked `excluded_reason = 'hand_checked_v1'`.
- **Questions:** M1: A "could they take your piece and come out ahead?" then, only if A is yes, B "could you have kept it
  safe?". M2: A "could you take their piece and come out ahead?".
- **Score:** a position is *real* only when every question asked is answered yes. "Can't tell" and "no" are not real.
  **Gate: real >= 27 of 30.** Each non-real position is listed with its numbers for the calibration decision in ADR 0006.

The page holds the owner's games: it lives under `data/` (git-ignored) and is never committed or published.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import chess
import chess.svg

from app import config
from app.db.schema import connect
from app.learner import seen
from app.learner.explorer import GREEN, NAMES, ORANGE, RED, TARGET, board_svg, plain, side

VERSION = 1
MARK = f"hand_checked_v{VERSION}"
STRATA = (("M1", "moved", 8), ("M1", "other", 7), ("M2", None, 15))
GATE = 27
ANSWERS = ("yes", "no", "cant")


def key_path() -> Path:
    return config.DATA_DIR / "evidence" / f"handcheck_v{VERSION}.json"


def page_path() -> Path:
    return config.DATA_DIR / "evidence" / f"handcheck_v{VERSION}.html"


def _order(salt: str, position_id: int) -> str:
    return hashlib.sha256(f"handcheck_v{VERSION}:{salt}:{position_id}".encode()).hexdigest()


def sample(conn) -> list[dict]:
    seen.propagate(conn)
    rows = conn.execute(
        "SELECT id, game_id, ply, mistake_type, evidence_json FROM position"
        " WHERE kind = 'MISTAKE' AND pool = 'PRACTICE' AND excluded_reason IS NULL AND " + seen.UNSEEN_BOARD
    ).fetchall()
    used: set[tuple] = set()
    picked = []
    for mtype, lost, n in STRATA:
        pool = [r for r in rows if r["mistake_type"] == mtype
                and (lost is None or json.loads(r["evidence_json"])["lost_piece"] == lost)]
        pool.sort(key=lambda r: _order("pick", r["id"]))
        taken = 0
        for r in pool:
            if taken == n:
                break
            if (r["game_id"], r["ply"]) in used:
                continue
            used.add((r["game_id"], r["ply"]))
            picked.append({"position_id": r["id"], "type": mtype, "lost_piece": lost})
            taken += 1
        if taken < n:
            raise SystemExit(f"only {taken} positions for {mtype} {lost or ''}; need {n}")
    picked.sort(key=lambda p: _order("show", p["position_id"]))
    for i, p in enumerate(picked, 1):
        p["id"] = f"hc-{i:02d}"
        p["questions"] = ["A", "B"] if p["type"] == "M1" else ["A"]
    return picked


def make(conn) -> Path:
    path = key_path()
    if path.exists():
        key = json.loads(path.read_text())
    else:
        items = sample(conn)
        key = {"version": VERSION, "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
               "gate": f"real >= {GATE} of {len(items)}", "items": items}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(key, indent=1) + "\n")
        for it in items:
            seen.mark_seen(conn, it["position_id"], MARK)
    seen.propagate(conn)  # also repairs boards marked before sibling rows were marked together
    cards = []
    for it in key["items"]:
        row = conn.execute("SELECT evidence_json, verified_alternatives_json FROM position WHERE id = ?",
                           (it["position_id"],)).fetchone()
        cards.append(card(it, json.loads(row["evidence_json"]), json.loads(row["verified_alternatives_json"] or "[]")))
    out = page_path()
    out.write_text(PAGE.replace("__CARDS__", "\n".join(cards)).replace("__TOTAL__", str(len(cards)))
                   .replace("__KEY__", f"handcheck_v{VERSION}"))
    return out


def line_words(board: chess.Board, ucis: list[str], me: chess.Color) -> str:
    """The line in plain words, each move labelled from the player's side (`me`)."""
    b = board.copy(stack=False)
    words = []
    for uci in ucis:
        who = "you" if b.turn == me else "they"
        words.append(f"{who}: {plain(b, uci)}")
        b.push(chess.Move.from_uci(uci))
    return "; ".join(words)


def buttons(item: str, q: str) -> str:
    labels = {"yes": "Yes", "no": "No", "cant": "Can't tell"}
    return (f'<div class="btns" data-item="{item}" data-q="{q}">'
            + "".join(f'<button data-v="{v}">{labels[v]}</button>' for v in ANSWERS) + "</div>")


def card(it: dict, e: dict, alts: list[dict]) -> str:
    board = chess.Board(e["fen"])
    me = board.turn
    played = chess.Move.from_uci(e["player_move"]["uci"])
    after = board.copy(stack=False)
    after.push(played)
    line = e["refutation_line"]["uci"]
    fill = {chess.parse_square(sq): TARGET for sq in e["target_squares"]}
    first_alt = chess.Move.from_uci(alts[0]["uci"]) if alts else None
    if it["type"] == "M1":
        reply = chess.Move.from_uci(line[0])
        lost_sq = e["lost_piece_square_after"]
        piece = NAMES[after.piece_at(chess.parse_square(lost_sq)).piece_type]
        arrows = [chess.svg.Arrow(played.from_square, played.to_square, color=RED)]
        if first_alt:
            arrows.append(chess.svg.Arrow(first_alt.from_square, first_alt.to_square, color=GREEN))
        boards = (f'<figure>{board_svg(board, me, arrows, fill)}<figcaption>Before your move</figcaption></figure>'
                  f'<figure>{board_svg(after, me, [chess.svg.Arrow(reply.from_square, reply.to_square, color=ORANGE)], {})}'
                  f'<figcaption>After your move</figcaption></figure>')
        story = (f"You were {side(me)}. You played <b>{html.escape(plain(board, played.uci()))}</b> (red). "
                 f"The engine says they can now play: {html.escape(line_words(after, line, me))} (orange: their first move).")
        qa = (f'<div class="q" data-qid="A"><p><b>A.</b> After your move, could they take your {piece} on {lost_sq} '
              f'and come out ahead (not lose as much back)?</p>{buttons(it["id"], "A")}</div>'
              f'<div class="q" data-qid="B"><p><b>B.</b> Could you have kept it safe instead? For example: '
              f'{html.escape(plain(board, first_alt.uci())) if first_alt else "another move"} (green).</p>'
              f'{buttons(it["id"], "B")}</div>')
    else:
        capture = chess.Move.from_uci(line[0])
        target = chess.square_name(capture.to_square)
        piece = NAMES[board.piece_at(capture.to_square).piece_type]
        arrows = [chess.svg.Arrow(played.from_square, played.to_square, color=RED),
                  chess.svg.Arrow(capture.from_square, capture.to_square, color=GREEN)]
        boards = f'<figure>{board_svg(board, me, arrows, fill)}<figcaption>Before your move</figcaption></figure>'
        story = (f"You were {side(me)}. You played <b>{html.escape(plain(board, played.uci()))}</b> (red). "
                 f"The engine says you could have played: {html.escape(line_words(board, line, me))} "
                 f"(green: your first move).")
        qa = (f'<div class="q" data-qid="A"><p><b>A.</b> Could you take their {piece} on {target} (green) and come out '
              f'ahead (they cannot win as much back)?</p>{buttons(it["id"], "A")}</div>')
    return (f'<section class="card" id="{it["id"]}"><h2>{it["id"]}</h2><div class="boards">{boards}</div>'
            f'<p class="show">{story}</p>{qa}</section>')


def parse_answers(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"^(hc-\d+):\s*(.+)$", text, re.MULTILINE):
        out[m.group(1)] = dict(re.findall(r"\b([AB])\s+(yes|no|cant|-)\b", m.group(2)))
    return out


def score(conn, answers_text: str) -> dict:
    key = json.loads(key_path().read_text())
    answers = parse_answers(answers_text)
    items, real, unanswered = [], 0, []
    for it in key["items"]:
        a = answers.get(it["id"], {})
        asked = ["A"] if a.get("A") != "yes" else it["questions"]
        if not a.get("A") or any(a.get(q) in (None, "-") for q in asked):
            unanswered.append(it["id"])
        is_real = all(a.get(q) == "yes" for q in it["questions"])
        real += is_real
        e = json.loads(conn.execute("SELECT evidence_json FROM position WHERE id = ?",
                                    (it["position_id"],)).fetchone()["evidence_json"])
        items.append({"id": it["id"], "type": it["type"], "lost_piece": it["lost_piece"], "answers": a,
                      "real": is_real, "eval_loss": e["eval_loss"], "eval_loss_stability": e["eval_loss_stability"],
                      "material_swing": e["material_swing"], "refutation_plies": len(e["refutation_line"]["uci"])})
    by_type = {}
    for t in ("M1", "M2"):
        rows = [i for i in items if i["type"] == t]
        by_type[t] = {"real": sum(i["real"] for i in rows), "of": len(rows)}
    result = {"version": VERSION, "scored_at": datetime.now(UTC).isoformat(timespec="seconds"),
              "real": real, "of": len(items), "gate": GATE, "passed": real >= GATE, "by_type": by_type,
              "unanswered": unanswered, "not_real": [i for i in items if not i["real"]], "items": items}
    out = key_path().with_name(f"handcheck_v{VERSION}_result.json")
    out.write_text(json.dumps(result, indent=1) + "\n")
    return result


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mistake Check</title><style>
:root{color-scheme:light dark;--bg:#fff;--fg:#1c1c1c;--card:#f5f5f2;--line:#d8d8d0;--accent:#2f6f4f}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--card:#222;--line:#444;--accent:#6fbf8f}}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.45 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:18px 0}
h1{font-size:22px} h2{font-size:18px;margin:0 0 .5em}
.boards{display:flex;gap:10px;flex-wrap:wrap}figure{margin:0;flex:1;min-width:220px;max-width:360px}
figure svg{width:100%;height:auto}figcaption{opacity:.7;font-size:.9em}
.show{background:rgba(120,120,120,.12);padding:8px 10px;border-radius:8px}
.q p{margin:.8em 0 .4em}.btns{display:flex;gap:8px;flex-wrap:wrap}
button{font:inherit;padding:10px 18px;border:2px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg);cursor:pointer}
button.on{background:var(--accent);border-color:var(--accent);color:#fff}
#bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:5}
#out{width:100%;height:200px;font:14px monospace}.note{opacity:.85}
.key b{padding:0 4px;border-radius:4px;color:#fff}.r{background:#d9534f}.o{background:#e08e0b}.g{background:#3c9a5f}.y{background:#c9a400}
</style></head><body><main>
<div id="bar"><b id="prog">0 of __TOTAL__ answered</b></div>
<h1>Is it a real mistake?</h1>
<p class="note">These are 30 moves from your own games that the mistake finder flagged. Please check whether each one is real,
from the board. <b>"Can't tell" is a fine answer</b>; nothing is timed and there are no tricks. Your answers are saved in this
browser, so you can stop and come back.</p>
<p class="note key">Arrows: <b class="r">red</b> your move · <b class="o">orange</b> their reply · <b class="g">green</b> a
better move or the free capture · <b class="y">yellow</b> the piece that mattered. "Come out ahead" means winning more than
you (or they) lose back.</p>
<p class="note">None of these positions will appear in your future tests: they all come from the practice pool.</p>
__CARDS__
<section class="card"><h2>When you are done</h2>
<p>Press the button and paste the text in the chat.</p>
<button id="copy">Copy my answers</button> <button id="dl">Download as a file</button>
<p><textarea id="out" readonly></textarea></p></section>
</main><script>
const KEY='__KEY__', total=__TOTAL__;
let ans={}; try{ans=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const need={};document.querySelectorAll('.btns').forEach(b=>{(need[b.dataset.item]=need[b.dataset.item]||[]).push(b.dataset.q)});
function paint(){document.querySelectorAll('.btns').forEach(b=>{const v=(ans[b.dataset.item]||{})[b.dataset.q];
 b.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.v===v))});
 document.querySelectorAll('.q[data-qid="B"]').forEach(q=>{const i=q.parentElement.id;q.style.display=((ans[i]||{}).A==='yes')?'':'none'});
 const done=Object.keys(need).filter(i=>{const a=ans[i]||{};return a.A&&(a.A!=='yes'||need[i].every(q=>a[q]))}).length;
 document.getElementById('prog').textContent=done+' of '+total+' answered';
 const lines=Object.keys(need).filter(i=>ans[i]).map(i=>i+': '+need[i].map(q=>q+' '+((ans[i]||{})[q]||'-')).join(', '));
 document.getElementById('out').value=lines.join('\\n');}
document.querySelectorAll('.btns button').forEach(x=>x.onclick=()=>{const p=x.parentElement,i=p.dataset.item;
 (ans[i]=ans[i]||{})[p.dataset.q]=x.dataset.v;try{localStorage.setItem(KEY,JSON.stringify(ans))}catch(e){};paint()});
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.select();
 try{navigator.clipboard.writeText(t.value)}catch(e){document.execCommand('copy')}};
document.getElementById('dl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([document.getElementById('out').value]));a.download='my_mistake_check.txt';a.click()};
paint();
</script></body></html>"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.learner.handcheck")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("make")
    s = sub.add_parser("score")
    s.add_argument("answers", type=Path)
    args = p.parse_args(argv)
    conn = connect()
    if args.cmd == "make":
        print(make(conn))
    else:
        r = score(conn, args.answers.read_text())
        print(json.dumps({k: r[k] for k in ("real", "of", "gate", "passed", "by_type", "unanswered")}, indent=1))
        for i in r["not_real"]:
            print(f"  not real: {i['id']} {i['type']} {i['lost_piece'] or ''} answers={i['answers']} "
                  f"loss={i['eval_loss']} swing={i['material_swing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
