"""Build a self-contained web page for the owner's hand-check (labels hidden, no notation needed).

Reads the item ids from handcheck_owner.md (so it shows exactly the same 30 items) and the positions
from positions.jsonl. The page contains only the board, the move, and a plain-English question; it never
includes a label or a category. Answers are saved in the browser and can be copied as text.

Run:  cd backend && uv run python ../evals/tools/make_handcheck_page.py
Out:  evals/sets/real_play_v1/handcheck_owner.html
"""

import html
import json
import re
from pathlib import Path

import chess
import chess.svg

SET = Path(__file__).resolve().parents[1] / "sets" / "real_play_v1"
NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook",
         chess.QUEEN: "queen", chess.KING: "king"}


def side(color):
    return "White" if color == chess.WHITE else "Black"


def plain_move(board, move):
    """'Black's knight takes the pawn on c2.' in plain words (no notation)."""
    piece = board.piece_at(move.from_square)
    to = chess.square_name(move.to_square)
    who = f"{side(board.turn)}'s {NAMES[piece.piece_type]}"
    if board.is_castling(move):
        return f"{side(board.turn)} castles."
    if board.is_en_passant(move):
        return f"{who} takes a pawn on {to} (en passant)."
    victim = board.piece_at(move.to_square)
    text = f"{who} takes the {NAMES[victim.piece_type]} on {to}" if victim else f"{who} moves to {to}"
    if move.promotion:
        text += f" and becomes a {NAMES[move.promotion]}"
    after = board.copy()
    after.push(move)
    if after.is_checkmate():
        text += " (checkmate)"
    elif after.is_check():
        text += " (check)"
    return text + "."


def card(n, total, r):
    board = chess.Board(r["fen"])
    move = chess.Move.from_uci(r["move_uci"])
    mover, other = board.turn, not board.turn
    sentence = plain_move(board, move)
    if r["detector"] == "missed_free":
        svg = chess.svg.board(board, orientation=mover, size=380,
                              arrows=[chess.svg.Arrow(move.from_square, move.to_square, color="#d9534fcc")])
        show = f"The board BEFORE the move. The red arrow is the move: {sentence}"
        questions = [
            ("A", (f"Could {side(mover)} win a piece here (a knight, bishop, rook or queen) for free, or win more "
                   "than it loses back? (A rook for a bishop counts. An even trade does not.)")),
            ("B", "Does the move shown (the red arrow) do that?"),
        ]
    else:
        after = board.copy()
        after.push(move)
        svg = chess.svg.board(after, orientation=mover, size=380, lastmove=move)
        show = f"The board AFTER the move. {sentence} The yellow squares show the move."
        questions = [
            ("A", (f"Can {side(other)} now win a piece (a knight, bishop, rook or queen) of {side(mover)}'s for "
                   "free, or win more than it loses back? (Pawns do not count.)")),
        ]
    qhtml = "".join(
        f'<div class="q" data-qid="{k}"><p><b>{k}.</b> {html.escape(t)}</p><div class="btns" data-item="{r["id"]}" data-q="{k}">'
        f'<button data-v="yes">Yes</button><button data-v="no">No</button>'
        f'<button data-v="can\'t tell">Can\'t tell</button></div></div>'
        for k, t in questions)
    return (f'<section class="card" id="{r["id"]}" data-kind="{r["detector"]}"><h2>Item {n} of {total} '
            f'<small>({r["id"]})</small></h2><p class="mover">{side(mover)} to move</p>'
            f'<div class="board">{svg}</div><p class="show">{html.escape(show)}</p>{qhtml}</section>')


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chess hand-check</title><style>
:root{color-scheme:light dark;--bg:#fff;--fg:#1c1c1c;--card:#f5f5f2;--line:#d8d8d0;--accent:#2f6f4f}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--card:#222;--line:#444;--accent:#6fbf8f}}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.45 system-ui,sans-serif}
main{max-width:640px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:18px 0}
h1{font-size:22px} h2{font-size:18px;margin:0} small{opacity:.6;font-weight:400}
.mover{font-weight:600;margin:.3em 0}.board svg{width:100%;height:auto;max-width:380px}
.show{background:rgba(120,120,120,.12);padding:8px 10px;border-radius:8px}
.q p{margin:.8em 0 .4em}.btns{display:flex;gap:8px;flex-wrap:wrap}
button{font:inherit;padding:10px 18px;border:2px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg);cursor:pointer}
button.on{background:var(--accent);border-color:var(--accent);color:#fff}
#bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:5}
#out{width:100%;height:200px;font:14px monospace} .note{opacity:.8}
</style></head><body><main>
<div id="bar"><b id="prog">0 of __TOTAL__ answered</b></div>
<h1>Chess hand-check</h1>
<p class="note">For each position, answer from the board. <b>Can't tell is a fine answer.</b> There are no tricks and nothing is timed.
Your answers are saved in this browser, so you can stop and come back. A free piece means you can capture it
and not lose more than you win back.</p>
__CARDS__
<section class="card"><h2>When you are done</h2>
<p>Press the button and send me the text it produces (paste it in the chat).</p>
<button id="copy">Copy my answers</button> <button id="dl">Download as a file</button>
<p><textarea id="out" readonly></textarea></p></section>
</main><script>
const KEY='handcheck_owner_v1', total=__TOTAL__;
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
document.getElementById('dl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([document.getElementById('out').value]));a.download='my_handcheck_answers.txt';a.click()};
paint();
</script></body></html>"""


def main():
    ids = re.findall(r"^## (rp1-\d+)", (SET / "handcheck_owner.md").read_text(), re.MULTILINE)
    by_id = {r["id"]: r for r in map(json.loads, (SET / "positions.jsonl").read_text().splitlines()) if r}
    cards = "\n".join(card(n, len(ids), by_id[i]) for n, i in enumerate(ids, 1))
    (SET / "handcheck_owner.html").write_text(PAGE.replace("__CARDS__", cards).replace("__TOTAL__", str(len(ids))))
    print(f"wrote handcheck_owner.html with {len(ids)} items")


if __name__ == "__main__":
    main()
