"""Hand-check page for the drill bank (ADR 0017 decision 9): 20 drills, one per game, 10 hanging-own-piece and 10 missed-free-piece.

  uv run python -m app.learner.drillcheck make                 # data/drills/drillcheck_v1.html (sample frozen on first run)
  uv run python -m app.learner.drillcheck score ANSWERS.txt    # gate: 18 of 20 real (90%, as the 27 of 30 of the earlier checks)

Same questions as `handcheck` (A: is the loss real; B, for hanging pieces: could it have been kept safe), applied to Lichess drills,
shown one position at a time with a board per question (a fragment: the Artifact tool wraps it). The sample is chosen by a hash of the drill id, so it does not depend on what the bank holds in what order.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import chess
import chess.svg

from app.learner import drillbank, drilltiming, handcheck

VERSION = 2  # v2: missed-free-piece drills carry a timing class (ADR 0017); v1 scored 16 of 20 and its drills are not reused
M2_QUOTA = {"right_away": 4, "next_move": 4, "within_3_moves": 2}
PER_TYPE = 10
GATE = 18
ID_PREFIX = "dc"


def previous_drill_ids() -> frozenset[str]:
    """Drills already shown in an earlier check version are not shown again."""
    ids: set[str] = set()
    for v in range(1, VERSION):
        p = drillbank.bank_dir() / f"drillcheck_v{v}_key.json"
        if p.exists():
            ids.update(i["drill_id"] for i in json.loads(p.read_text())["items"])
    return frozenset(ids)


def key_path() -> Path:
    return drillbank.bank_dir() / f"drillcheck_v{VERSION}_key.json"


def page_path() -> Path:
    return drillbank.bank_dir() / f"drillcheck_v{VERSION}.html"


def _order(drill: dict) -> str:
    return hashlib.sha256(f"drillcheck-v{VERSION}|{drill['id']}".encode()).hexdigest()


def sample(drills: list[dict], timing: dict[str, str] | None = None, exclude: frozenset[str] = frozenset(),
           per_type: int = PER_TYPE) -> list[dict]:
    """`per_type` drills of each type by hash order, never two from one game, never an experimental or excluded drill.

    M2 drills need a timing class other than `unclear` and follow M2_QUOTA (right away 4, next move 4, within 3 moves 2); a class
    with too few drills is topped up from the others. Without `timing` (tests of M1 only) M2 is sampled without classes.
    """
    out: list[dict] = []
    used: set[str] = set()

    def pool(t):
        return sorted((d for d in drills if d["type"] == t and not d["experimental"] and d["id"] not in exclude), key=_order)

    def take(candidates, n):
        got = 0
        for d in candidates:
            if got >= n:
                break
            if d["game_id"] in used:
                continue
            used.add(d["game_id"])
            out.append(d)
            got += 1
        return got

    take(pool("M1"), per_type)
    if timing is None:
        take(pool("M2"), per_type)
        return out
    m2 = [d for d in pool("M2") if timing.get(d["id"], "unclear") != "unclear"]
    got = sum(take([d for d in m2 if timing[d["id"]] == c], n) for c, n in M2_QUOTA.items())
    take([d for d in m2 if timing[d["id"]] in ("right_away", "next_move")], per_type - got)
    return out


def questions(d: dict) -> list[str]:
    return ["A", "B"] if d["type"] == "M1" else ["A"]


def render_card(it: dict, d: dict, timing: str | None = None) -> str:
    """One position as a card: each question carries its own board and one plain sentence (A first, B only after a yes to A)."""
    e, alts = d["evidence"], d["alternatives"]
    board = chess.Board(e["fen"])
    me = board.turn
    who = handcheck.side(me)
    played = chess.Move.from_uci(e["player_move"]["uci"])
    played_words = html.escape(handcheck.plain(board, played.uci()))
    after = board.copy(stack=False)
    after.push(played)
    line = e["refutation_line"]["uci"]
    fill = {chess.parse_square(sq): handcheck.TARGET for sq in e["target_squares"]}
    red = chess.svg.Arrow(played.from_square, played.to_square, color=handcheck.RED)
    qs = []
    if d["type"] == "M1":
        reply = chess.Move.from_uci(line[0])
        lost_sq = e["lost_piece_square_after"]
        piece = handcheck.NAMES[after.piece_at(chess.parse_square(lost_sq)).piece_type]
        took = board.piece_at(played.to_square) if board.is_capture(played) else None
        note = f" (Count the {handcheck.NAMES[took.piece_type]} your move took.)" if took else ""
        orange = chess.svg.Arrow(reply.from_square, reply.to_square, color=handcheck.ORANGE)
        qs.append(("A", handcheck.board_svg(after, me, [red, orange], {}),
                   f"You are <b>{who}</b>. You played <b>{played_words}</b> <i class=\"r\">(red)</i>.",
                   f"Can they now win your {piece} on {lost_sq} <i class=\"o\">(orange)</i> and come out ahead?{note}",
                   handcheck.line_words(after, line, me)))
        if alts:
            alt = chess.Move.from_uci(alts[0]["uci"])
            green = chess.svg.Arrow(alt.from_square, alt.to_square, color=handcheck.GREEN)
            qs.append(("B", handcheck.board_svg(board, me, [red, green], fill),
                       "The same position, before your move.",
                       (f"Could you have kept it safe instead? For example <b>{html.escape(handcheck.plain(board, alt.uci()))}</b> "
                        "<i class=\"g\">(green)</i>."), None))
    else:
        capture = chess.Move.from_uci(line[0])
        target = chess.square_name(capture.to_square)
        piece = handcheck.NAMES[board.piece_at(capture.to_square).piece_type]
        green = chess.svg.Arrow(capture.from_square, capture.to_square, color=handcheck.GREEN)
        qs.append(("A", handcheck.board_svg(board, me, [red, green], fill),
                   f"You are <b>{who}</b>. You played <b>{played_words}</b> <i class=\"r\">(red)</i>.",
                   m2_question(timing, piece, target), handcheck.line_words(board, line, me)))
    out = []
    for qid, svg, setup, ask, line_text in qs:
        more = (f'<details><summary>Show the moves</summary><p>{html.escape(line_text)}</p></details>' if line_text else "")
        out.append(f'<div class="q" data-qid="{qid}" hidden><figure>{svg}</figure><p class="setup">{setup}</p>'
                   f'<p class="ask">{ask}</p>{more}<div class="btns" data-item="{it["id"]}" data-q="{qid}">'
                   '<button data-v="yes" class="yes">Yes<kbd>Y</kbd></button><button data-v="no" class="no">No<kbd>N</kbd></button>'
                   '<button data-v="cant" class="cant">Can\'t tell<kbd>C</kbd></button></div></div>')
    return f'<section class="card" id="{it["id"]}" data-qs="{"".join(q[0] for q in qs)}" hidden>{"".join(out)}</section>'


M2_WORDS = {
    "right_away": "Could you win material right away? Take their {piece} on {sq} <i class=\"g\">(green)</i>. Even if they can take it back, "
                  "you are then at least 3 points ahead.",
    "next_move": "Could you win material on your next move? Take their {piece} on {sq} <i class=\"g\">(green)</i>. They can take it back, "
                 "but then your next move wins something, and you end up at least 3 points ahead.",
    "within_3_moves": "Could you win material within your next 3 moves? Take their {piece} on {sq} <i class=\"g\">(green)</i>. "
                      "It takes up to 3 of your moves, and you end up at least 3 points ahead.",
}
POINTS_NOTE = "Points: pawn 1, knight or bishop 3, rook 5, queen 9."


def m2_question(timing: str | None, piece: str, sq: str) -> str:
    text = M2_WORDS.get(timing or "", M2_WORDS["right_away"]).format(piece=piece, sq=sq)
    return f"{text} <span class=\"pts\">{POINTS_NOTE}</span>"


def make(bank: Path | None = None) -> Path:
    bank = bank or drillbank.bank_path()
    drills = [json.loads(line) for line in bank.open()]
    timing = drilltiming.read_timing()
    if key_path().exists():
        key = json.loads(key_path().read_text())
        by_id = {d["id"]: d for d in drills}
        chosen = [by_id[i["drill_id"]] for i in key["items"]]
    else:
        chosen = sample(drills, timing, previous_drill_ids())
        items = [{"id": f"{ID_PREFIX}-{n:02d}", "drill_id": d["id"], "type": d["type"], "game_id": d["game_id"],
                  "avg_rating": d["avg_rating"], "questions": questions(d), "timing": timing.get(d["id"])}
                 for n, d in enumerate(chosen, 1)]
        key_path().write_text(json.dumps({"version": VERSION, "gate": GATE, "items": items}, indent=1) + "\n")
    key = json.loads(key_path().read_text())
    cards = "\n".join(render_card({"id": it["id"], "type": it["type"]}, d, it.get("timing")) for it, d in zip(key["items"], chosen, strict=True))
    page = PAGE.replace("__CARDS__", cards).replace("__TOTAL__", str(len(chosen))).replace("__KEY__", f"drillcheck_v{VERSION}")
    page_path().write_text(page)
    return page_path()


PAGE = r"""<title>Drill Check</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=Figtree:wght@400;500;600&display=swap">
<style>
/* One position at a time: a large board, one plain sentence, three large answer buttons. */
:root{--bg:#eef2f0;--surface:#fff;--fg:#17201d;--muted:#5a6762;--line:#d3dbd7;--accent:#1f6f5c;
 --yes:#1d7a4b;--no:#b3423a;--cant:#5a6762;--red:#d9534f;--orange:#c77a08;--green:#2e8b57;
 --display:'Bricolage Grotesque','Avenir Next',system-ui,sans-serif;--body:'Figtree',system-ui,-apple-system,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e1514;--surface:#172120;--fg:#e8efec;--muted:#9aa9a4;
 --line:#2b3a37;--accent:#5ec2a6;--yes:#46b97c;--no:#e0736b;--cant:#9aa9a4;--red:#ef7873;--orange:#e5a13a;--green:#58c28a;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0e1514;--surface:#172120;--fg:#e8efec;--muted:#9aa9a4;--line:#2b3a37;--accent:#5ec2a6;
 --yes:#46b97c;--no:#e0736b;--cant:#9aa9a4;--red:#ef7873;--orange:#e5a13a;--green:#58c28a;color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:18px/1.5 var(--body);padding-block:16px 40px;
 padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
main{max-width:560px;margin:0 auto;display:flex;flex-direction:column;gap:16px}
h1{font:700 26px/1.15 var(--display);margin:0;text-wrap:balance}
.muted{color:var(--muted);font-size:16px;margin:0}
#steps{display:grid;grid-template-columns:repeat(20,1fr);gap:3px}
#steps i{height:6px;border-radius:3px;background:var(--line)}
#steps i.done{background:var(--accent)}#steps i.now{background:var(--fg)}
#count{font-weight:600;font-size:15px;color:var(--muted);display:flex;justify-content:space-between}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px}
.q{display:flex;flex-direction:column;gap:12px;min-width:0}
figure{margin:0}figure svg{display:block;width:100%;height:auto;border-radius:6px}
.setup{margin:0;color:var(--muted);font-size:16px}
.pts{display:block;margin-top:6px;font:400 15px var(--body);color:var(--muted)}
.ask{margin:0;font:600 21px/1.3 var(--display);text-wrap:balance}
i.r{color:var(--red);font-style:normal;font-weight:600}i.o{color:var(--orange);font-style:normal;font-weight:600}i.g{color:var(--green);font-style:normal;font-weight:600}
details{font-size:16px;color:var(--muted)}summary{cursor:pointer;padding:4px 0}details p{margin:4px 0 0}
.btns{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.btns button{font:600 20px var(--body);padding:18px 10px;border-radius:12px;border:2px solid var(--line);background:var(--surface);
 color:var(--fg);cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:2px}
.btns .cant{grid-column:1/-1;padding:14px 10px;font-size:18px}
.btns .yes{border-color:var(--yes);color:var(--yes)}.btns .no{border-color:var(--no);color:var(--no)}.btns .cant{color:var(--cant)}
.btns button.on.yes{background:var(--yes)}.btns button.on.no{background:var(--no)}.btns button.on.cant{background:var(--cant)}
.btns button.on{color:var(--bg)}
button kbd{font:500 12px var(--body);opacity:.65}
button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.nav{display:flex;justify-content:space-between}
.nav button,#copy{font:500 16px var(--body);background:none;border:0;color:var(--muted);padding:10px 4px;cursor:pointer;text-decoration:underline}
#copy{font:600 19px var(--body);text-decoration:none;background:var(--accent);color:var(--bg);border-radius:12px;padding:16px;width:100%}
#out{width:100%;min-height:200px;font:14px ui-monospace,Menlo,monospace;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:10px;padding:10px}
@media (prefers-reduced-motion:no-preference){.card{animation:in .18s ease-out}@keyframes in{from{opacity:.4;transform:translateY(6px)}}}
</style>
<main>
 <div id="head"><h1>Is it a real mistake?</h1>
  <p class="muted" style="margin-top:8px">20 moves from other players' games (public Lichess games). Look at the board, read the question, tap an answer.
  <b>"Can't tell" is fine.</b> It moves on by itself, and your answers are kept if you leave.</p></div>
 <div><div id="count"><span id="pos"></span><span id="doneN"></span></div><div id="steps"></div></div>
 __CARDS__
 <section class="card" id="end" hidden><div class="q"><h1>All done</h1>
  <p class="muted">Tap the button, then paste the text into the chat with Claude.</p>
  <button id="copy">Copy my answers</button><textarea id="out" readonly aria-label="Your answers"></textarea></div></section>
 <div class="nav"><button id="back">&larr; Back</button><button id="skip">Skip &rarr;</button></div>
</main>
<script>
const KEY='__KEY__', TOTAL=__TOTAL__, VAL={y:'yes',n:'no',c:'cant'};
let ans={}; try{ans=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const cards=[...document.querySelectorAll('section.card[data-qs]')], ids=cards.map(c=>c.id);
const qsOf=i=>document.getElementById(i).dataset.qs.split('');
function needed(i){const a=ans[i]||{},n=['A'];if(a.A==='yes'&&qsOf(i).includes('B'))n.push('B');return n}
function active(i){const a=ans[i]||{};return needed(i).find(q=>!a[q])||null}
const complete=i=>active(i)===null;
function save(){try{localStorage.setItem(KEY,JSON.stringify(ans))}catch(e){}}
let pos=0;
const steps=document.getElementById('steps');ids.forEach(()=>steps.appendChild(document.createElement('i')));
function set(i,q,v){const a=(ans[i]=ans[i]||{});a[q]=v;if(q==='A'&&v!=='yes')delete a.B;save();paint();
 if(complete(i)){setTimeout(()=>{if(ids[pos]===i){pos++;paint();window.scrollTo(0,0)}},280)}}
function paint(){
 const cur=pos<ids.length;
 cards.forEach((c,k)=>{c.hidden=k!==pos});document.getElementById('end').hidden=cur;
 document.getElementById('head').hidden=pos>0||Object.keys(ans).length>0;
 if(cur){const i=ids[pos],show=active(i)||needed(i).slice(-1)[0],a=ans[i]||{};
  cards[pos].querySelectorAll('.q').forEach(q=>{q.hidden=q.dataset.qid!==show;
   q.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b.dataset.v===a[q.dataset.qid]))})}
 const done=ids.filter(complete).length;
 steps.querySelectorAll('i').forEach((el,k)=>{el.className=complete(ids[k])?'done':(k===pos?'now':'')});
 document.getElementById('pos').textContent=cur?'Position '+(pos+1)+' of '+TOTAL:'Finished';
 document.getElementById('doneN').textContent=done+' answered';
 document.getElementById('out').value=ids.filter(i=>ans[i]).map(i=>i+': '+qsOf(i).map(q=>q+' '+((ans[i]||{})[q]||'-')).join(', ')).join('\n');
 document.getElementById('back').disabled=pos===0;document.getElementById('skip').disabled=!cur;
}
document.querySelectorAll('.btns button').forEach(b=>b.onclick=()=>{const p=b.parentElement;if(ids[pos]===p.dataset.item)set(p.dataset.item,p.dataset.q,b.dataset.v)});
document.addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA'||e.metaKey||e.ctrlKey||e.altKey)return;const k=e.key.toLowerCase();
 if(VAL[k]&&pos<ids.length){const i=ids[pos];set(i,active(i)||needed(i).slice(-1)[0],VAL[k]);e.preventDefault()}
 else if(k==='arrowleft'){if(pos>0){pos--;paint()}e.preventDefault()}
 else if(k==='arrowright'){if(pos<ids.length){pos++;paint()}e.preventDefault()}});
document.getElementById('back').onclick=()=>{if(pos>0){pos--;paint()}};
document.getElementById('skip').onclick=()=>{if(pos<ids.length){pos++;paint()}};
document.getElementById('copy').onclick=async()=>{const t=document.getElementById('out'),b=document.getElementById('copy');
 try{await navigator.clipboard.writeText(t.value);b.textContent='Copied. Paste it in the chat.'}catch(e){t.select();b.textContent='Select the text below and copy it'}};
const first=ids.findIndex(i=>!complete(i));pos=first<0?ids.length:first;paint();
</script>"""


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
