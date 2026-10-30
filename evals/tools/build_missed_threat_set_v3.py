"""Build the M3 eval set `missed_threat_v3` from real Lichess games, following sets/missed_threat_v3/LABEL_RULE.md. Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/build_missed_threat_set_v3.py [--pgn PATH] [--data DIR]

Reads the games sample made by lichess_stream_sample.py, labels positions with python-chess, the exchange search of
build_real_play_set.py and Stockfish at depth 14, and writes (in evals/sets/missed_threat_v3/): candidates.jsonl (all items, engine
labels), provenance.json, and the owner's check page + key (check_page.html, check_key.json: the key is private, git-ignored).
It does not freeze: freezing happens after the owner's answers (LABEL_RULE.md, "The owner's check").
"""

import argparse
import hashlib
import html
import json
import random
import sys
from pathlib import Path

import chess
import chess.pgn
import chess.svg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_missed_threat_set as V
from build_real_play_set import Engine
from make_handcheck_page import plain_move, side

ROOT = V.ROOT
OUT = ROOT / "evals" / "sets" / "missed_threat_v3"
SEED = 20261030
QUOTA = {"missed": 30, "uncertain": 15, "met": 25, "not_applicable": 30}
CHECK = {"missed": 8, "uncertain": 6, "met": 5, "not_applicable": 5}
CALM = 400
LOSS, MET_LOSS, FTL_ABS, FTL_SHARE, FTL_LOW, AVOID = 300, 100, 250, 0.6, 100, 100
THREAT_CP, NO_THREAT_CP = 200, 60


def score_after(F, board):
    """Mover-side depth-14 score of `board` (any side to move), mate/end handled."""
    if board.is_checkmate():
        return 10000 if board.turn != F.mover else -10000
    if board.is_game_over():
        return 0
    return V.cp(F.engine.analyse(board, V.ORACLE, perspective=F.mover))


def classify(engine, board, move, ply):
    """(label, facts dict) for the position, or None if it does not qualify for any label."""
    if not V.usable(board):
        return None
    P = V.passed(board)
    threats = V.static_threats(P)
    F = V.Facts(engine, board)
    if abs(F.best_cp) > CALM:
        return None
    base = {"best_cp": F.best_cp}
    if not threats:
        if F.threat_cp >= NO_THREAT_CP:
            return None
        loss = F.loss(move)
        if loss >= LOSS or loss < MET_LOSS:
            return ("not_applicable", {**base, "loss_cp": loss, "blunder": loss >= LOSS})
        return None
    if F.threat_cp < THREAT_CP:
        return None
    # T: the engine's best move for the opponent after the pass, if it is one of the static threats; else the biggest static win.
    pv = engine.analyse(P, V.ORACLE, perspective=P.turn).pv
    T = chess.Move.from_uci(pv[0]) if pv and chess.Move.from_uci(pv[0]) in threats else max(threats, key=lambda m: V.B.capture_net(P, m))
    loss = F.loss(move)
    facts = {**base, "loss_cp": loss, "threat_move": T.uci(), "threat_cp": F.threat_cp}
    if loss < MET_LOSS:
        return ("met", facts)
    if loss < LOSS:
        return None
    after = board.copy()
    after.push(move)
    if T not in after.legal_moves:
        return None  # M stopped T yet lost 300+: another mistake; not a case this set labels
    forced = after.copy()
    forced.push(T)
    ftl = F.best_cp - score_after(F, forced)
    facts["ftl_cp"] = ftl
    if ftl < FTL_LOW:
        return ("uncertain", facts)
    if ftl < max(FTL_ABS, FTL_SHARE * loss):
        return None
    B = chess.Move.from_uci(F.best.pv[0])
    bb = board.copy()
    bb.push(B)
    avoidable = T not in bb.legal_moves
    if not avoidable:
        bb.push(T)
        avoidable = F.best_cp - score_after(F, bb) < AVOID
    return ("missed", facts) if avoidable else None


def games(path):
    with open(path) as f:
        while (g := chess.pgn.read_game(f)) is not None:
            yield g


def card(n, total, r):
    board = chess.Board(r["fen"])
    move = chess.Move.from_uci(r["move_uci"])
    X, Y = side(board.turn), side(not board.turn)
    svg = chess.svg.board(board, orientation=board.turn, size=340, arrows=[chess.svg.Arrow(move.from_square, move.to_square, color="#d9534fcc")])
    qs = {"A": f"Imagine {X} does nothing this turn and {Y} moves next. Can {Y} win a piece or checkmate? (An even trade does not count.)",
          "B": f"Now {X} plays the real move (the red arrow). Can {Y} still do that?",
          "C": f"Was there a {X} move that stops it?",
          "D": f"Does {X}'s move lose something else?"}
    return (f'<section class="card" data-id="{r["id"]}" data-q="{html.escape(json.dumps(qs))}" hidden><p class="n">{n} of {total}</p>'
            f'<div class="board">{svg}</div><p class="mv">Red arrow = the move {X} played. {html.escape(plain_move(board, move))}</p></section>')


PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>M3 check</title>
<style>body{font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:12px;background:#fff;color:#111}
.n{color:#666;margin:4px 0}.board svg{max-width:100%;height:auto}.mv{font-size:15px;color:#333}
#q{font-size:20px;font-weight:600;margin:14px 0}.row{display:flex;gap:8px}.row button{flex:1;padding:16px 4px;font-size:18px;border-radius:10px;border:1px solid #888;background:#f4f4f4}
.row button:active{background:#ddd}#bar{height:6px;background:#eee;border-radius:3px}#fill{height:6px;background:#2a7;border-radius:3px;width:0}
#back{margin-top:12px;background:none;border:none;color:#06c;font-size:15px}textarea{width:100%;height:160px;font-size:14px}#done button{padding:14px;font-size:18px;width:100%}</style>
<h2>Quick check</h2><div id="bar"><div id="fill"></div></div>
<div id="stage">@@CARDS@@<div id="q"></div><div class="row" id="btns"><button data-v="yes">Yes</button><button data-v="no">No</button><button data-v="cant">Can't tell</button></div><button id="back">&larr; back</button></div>
<div id="done" hidden><h3>All done. Thank you!</h3><p>Tap the button, then paste what it copied into the chat.</p><button id="copy">Copy my answers</button><textarea id="out" readonly></textarea></div>
<script>
const S='m3v3check2',cards=[...document.querySelectorAll('.card')];let ans={},i=0,k='A';
try{ans=JSON.parse(localStorage.getItem(S)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(S,JSON.stringify(ans))}catch(e){}};
function next(c){const a=ans[c.dataset.id]||{};
 if(k==='A')return a.A==='yes'?'B':null; if(k==='B')return a.B==='yes'?'C':null; if(k==='C')return a.C==='yes'?'D':null; return null}
function show(){if(i>=cards.length){document.getElementById('stage').hidden=true;document.getElementById('done').hidden=false;
 document.getElementById('fill').style.width='100%';
 document.getElementById('out').value=Object.keys(ans).sort().map(id=>id+' '+Object.entries(ans[id]).map(([q,v])=>q+'='+({yes:'y',no:'n',cant:'?'})[v]).join(' ')).join('\\n');return}
 cards.forEach((c,j)=>c.hidden=j!==i);const c=cards[i];
 document.getElementById('q').textContent=k+'. '+JSON.parse(c.dataset.q)[k];
 document.getElementById('fill').style.width=(100*i/cards.length)+'%'}
document.getElementById('btns').onclick=e=>{const v=e.target.dataset.v;if(!v)return;const c=cards[i];
 (ans[c.dataset.id]=ans[c.dataset.id]||{})[k]=v;save();const n=next(c);if(n){k=n}else{i++;k='A';const t=cards[i];if(t)delete ans[t.dataset.id]}show()};
document.getElementById('back').onclick=()=>{if(k!=='A'){k=String.fromCharCode(k.charCodeAt(0)-1)}else if(i>0){i--;const a=ans[cards[i].dataset.id]||{};k=a.D?'D':a.C?'C':a.B?'B':'A'}show()};
document.getElementById('copy').onclick=()=>{const o=document.getElementById('out');o.select();try{navigator.clipboard.writeText(o.value)}catch(e){}};
show();
</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path.home() / "Projects" / "ai-chess-generator-coach" / "data"))
    ap.add_argument("--pgn")
    ap.add_argument("--reuse", action="store_true", help="skip the search; rebuild the page and key from candidates.jsonl")
    a = ap.parse_args()
    pgn = Path(a.pgn) if a.pgn else Path(a.data) / "lichess" / "rapid_600_1200_2026-09.pgn"
    if (OUT / "FROZEN.md").exists():
        sys.exit("missed_threat_v3 is frozen. Build a new version instead.")
    if a.reuse:
        return finish([json.loads(x) for x in (OUT / "candidates.jsonl").read_text().splitlines()], pgn, "Stockfish (see candidates)")
    rng = random.Random(SEED)
    gl = list(games(pgn))
    rng.shuffle(gl)
    got = {k: [] for k in QUOTA}
    with Engine() as engine:
        for g in gl:
            if all(len(got[k]) >= QUOTA[k] for k in QUOTA):
                break
            moves = list(g.mainline_moves())
            plies = [p for p in range(V.MIN_PLY, len(moves) - 1)]
            rng.shuffle(plies)
            for p in plies[:12]:
                board = g.board()
                for m in moves[:p]:
                    board.push(m)
                board = chess.Board(board.fen())
                res = classify(engine, board, moves[p], p)
                if res and len(got[res[0]]) < QUOTA[res[0]] and (res[0] != "not_applicable" or sum(
                        1 for r in got["not_applicable"] if r["blunder"] == res[1]["blunder"]) < QUOTA["not_applicable"] // 2):
                    label, facts = res
                    got[label].append({"label": label, "fen": board.fen(), "move_uci": moves[p].uci(), "move_san": board.san(moves[p]),
                                       "ply": p, "game": g.headers.get("Site", ""), "band": (min(int(g.headers["WhiteElo"]), int(g.headers["BlackElo"])) // 200) * 200,
                                       "constructed": False, **facts})
                    break
        engine_name = engine.name
    items = [r for k in QUOTA for r in got[k]]
    random.Random(SEED + 1).shuffle(items)
    for i, r in enumerate(items, 1):
        r["id"] = f"mt3-{i:03d}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "candidates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in items))
    finish(items, pgn, engine_name)


def finish(items, pgn, engine_name):
    got = {k: [r for r in items if r["label"] == k] for k in QUOTA}
    srng = random.Random(SEED + 2)
    sample = [r for k in CHECK for r in srng.sample(got[k], min(CHECK[k], len(got[k])))]
    srng.shuffle(sample)
    (OUT / "check_page.html").write_text(PAGE.replace("@@CARDS@@", "".join(card(i, len(sample), r) for i, r in enumerate(sample, 1))))
    (OUT / "check_key.json").write_text(json.dumps({r["id"]: r["label"] for r in sample}, indent=1) + "\n")
    prov = {"set": "missed_threat_v3", "rule": "LABEL_RULE.md", "seed": SEED, "engine": engine_name, "oracle_depth": V.ORACLE.depth,
            "games_file": pgn.name, "games_file_sha256": hashlib.sha256(pgn.read_bytes()).hexdigest(),
            "counts": {k: len(v) for k, v in got.items()}, "quota": QUOTA, "check_sample": len(sample), "detectors_run": False, "frozen": False}
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    print(json.dumps(prov["counts"]), "check:", len(sample))

if __name__ == "__main__":
    main()
