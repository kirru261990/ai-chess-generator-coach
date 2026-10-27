"""M3 hand-check (TASKS M3d; ADR 0011): the owner judges 30 flagged missed threats from older games. Gate: at least 27 are real.

  uv run python -m app.learner.handcheck_m3 scan [--db PATH] [--workers 4]   # run the M3 detector on older games until each time control has enough flags
  uv run python -m app.learner.handcheck_m3 make                              # sample once, write data/evidence/handcheck_m3_v1.html
  uv run python -m app.learner.handcheck_m3 score ANSWERS.txt                 # score the owner's copied answers

Rules fixed before the owner answers (so the result cannot move the goalposts):
- **Games:** only games *older* than the M3 real-game window, so the sample never touches the games the M3 rates will use
  (`realgame_rates freeze`). With no window frozen yet, older means every game before the latest `WINDOW_GAMES` of its time
  control; once the window is frozen, every game played before its earliest game. Games are scanned in a fixed pseudo-random order.
- **Flags:** `missed_threat` v1 findings of outcome `missed`, counted the way the rates count them (a repeat of the same standing
  threat is not a flag). At most one flag per game; `PER_TC` (15) per time control, 30 in all, shown in a fixed pseudo-random order.
  The sample is frozen in `data/evidence/handcheck_m3_v1.json` the first time; `make` afterwards only rebuilds the page.
- **Questions** (plain words, from the board): A "if you had skipped your turn, could they win material or give checkmate with
  this move?"; B (only if A is yes) "after the move you played, can they still do it?"; C (only if B is yes) "could you have
  stopped it with another move, for example the green one?".
- **Score:** a flag is *real* only when A, B and C are all yes. "Can't tell" and "no" are not real. **Gate: real >= 27 of 30.**
  Every non-real flag is listed with its numbers, kind and origin.

The page holds the owner's games: it lives under `data/` (git-ignored) and is never committed or published.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import multiprocessing as mp
import re
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import chess
import chess.svg

from app import config
from app.db.schema import connect, default_path
from app.learner import pools, realgame, realgame_rates
from app.learner.evidence_run import games_path
from app.learner.explorer import GREEN, ORANGE, RED, board_svg, plain, side
from app.learner.handcheck import ANSWERS, GATE, line_words

VERSION = 1
PER_TC = 15
QUESTIONS = ("A", "B", "C")


def evidence_dir() -> Path:
    return config.DATA_DIR / "evidence"


def scan_path() -> Path:
    return evidence_dir() / f"handcheck_m3_v{VERSION}_scan.jsonl"


def key_path() -> Path:
    return evidence_dir() / f"handcheck_m3_v{VERSION}.json"


def page_path() -> Path:
    return evidence_dir() / f"handcheck_m3_v{VERSION}.html"


def _order(salt: str, key: str) -> str:
    return hashlib.sha256(f"handcheck_m3_v{VERSION}:{salt}:{key}".encode()).hexdigest()


# --- which games ----------------------------------------------------------------------------------------------------------

def older_games(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """{time control: game ids older than the M3 window, in scan order}. Never a game in or after the window."""
    out: dict[str, list[str]] = {}
    frozen = {w["time_control"]: w for w in realgame.frozen_windows(conn, "M3")}
    tcs = [r[0] for r in conn.execute("SELECT DISTINCT time_control FROM game WHERE user_color IS NOT NULL ORDER BY time_control")]
    for tc in tcs:
        if tc in frozen:
            ids = frozen[tc]["game_ids"]
            marks = ",".join("?" * len(ids))
            cutoff = conn.execute(f"SELECT MIN(played_at) FROM game WHERE id IN ({marks})", ids).fetchone()[0] if ids else None
        else:
            row = conn.execute(
                "SELECT played_at FROM game WHERE time_control = ? AND user_color IS NOT NULL ORDER BY played_at DESC, id"
                " LIMIT 1 OFFSET ?", (tc, realgame.WINDOW_GAMES - 1)).fetchone()
            cutoff = row[0] if row else None
        if cutoff is None:  # fewer games than a window: nothing is older
            out[tc] = []
            continue
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM game WHERE time_control = ? AND user_color IS NOT NULL AND played_at < ?", (tc, cutoff))]
        out[tc] = sorted(ids, key=lambda g: _order("scan", g))
    return out


# --- scanning ---------------------------------------------------------------------------------------------------------------

def read_scan() -> dict[str, dict]:
    path = scan_path()
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["game"]: r for r in rows}


def flags_by_tc(scanned: dict[str, dict]) -> dict[str, int]:
    """Time control -> number of scanned games with at least one flag."""
    out: dict[str, int] = {}
    for r in scanned.values():
        if r["flags"]:
            out[r["time_control"]] = out.get(r["time_control"], 0) + 1
    return out


def _process(task: dict) -> dict:
    analyser = realgame_rates._worker["analyser"]
    started = time.monotonic()
    found: list[dict] = []
    try:
        realgame_rates.analyse_game(task["pgn"], task["user_color"], analyser, ("M3",), collect=found)
        error = None
    except ValueError as e:
        error = f"{type(e).__name__}: {e}"
    return {"game": task["game"], "time_control": task["time_control"], "flags": found, "error": error,
            "config_id": analyser.config.id, "seconds": time.monotonic() - started}


def scan(db_path: Path, workers: int) -> dict:
    conn = connect(db_path)
    pools.import_games(conn, games_path(), config.case_study_time_controls())
    older = older_games(conn)
    scanned = read_scan()
    ctx = mp.get_context("spawn")
    evidence_dir().mkdir(parents=True, exist_ok=True)
    with ctx.Pool(workers, initializer=realgame_rates._init_worker, initargs=(str(db_path),)) as pool:
        for tc, ids in older.items():
            while flags_by_tc(scanned).get(tc, 0) < PER_TC:
                batch = [g for g in ids if g not in scanned][: workers * 2]
                if not batch:
                    print(f"  {tc}: all {len(ids)} older games scanned, {flags_by_tc(scanned).get(tc, 0)} with a flag", flush=True)
                    break
                tasks = []
                for gid in batch:
                    r = conn.execute("SELECT pgn, user_color FROM game WHERE id = ?", (gid,)).fetchone()
                    tasks.append({"game": gid, "time_control": tc, "pgn": r["pgn"], "user_color": r["user_color"]})
                with scan_path().open("a") as out:
                    for res in pool.imap_unordered(_process, tasks):
                        if res["error"]:
                            print(f"  could not read a game: {res['error']}", flush=True)
                            continue
                        scanned[res["game"]] = res
                        out.write(json.dumps(res) + "\n")
                print(f"  {tc}: {len([g for g in ids if g in scanned])}/{len(ids)} older games scanned, "
                      f"{flags_by_tc(scanned).get(tc, 0)} with a flag", flush=True)
    return {"older_games": {tc: len(v) for tc, v in older.items()}, "with_flag": flags_by_tc(scanned)}


# --- the sample -------------------------------------------------------------------------------------------------------------

def sample(scanned: dict[str, dict]) -> list[dict]:
    """PER_TC flagged moves per time control, one per game, then all of them in a fixed pseudo-random order."""
    by_tc: dict[str, list[dict]] = {}
    for gid in sorted(scanned, key=lambda g: _order("pick", g)):
        r = scanned[gid]
        if r["flags"]:
            flag = min(r["flags"], key=lambda f: _order("flag", f"{gid}:{f['ply']}"))
            by_tc.setdefault(r["time_control"], []).append({"game": gid, "time_control": r["time_control"], "flag": flag})
    picked: list[dict] = []
    for tc in sorted(by_tc):
        if len(by_tc[tc]) < PER_TC:
            raise SystemExit(f"only {len(by_tc[tc])} flagged games at {tc}; need {PER_TC} (run `scan` again)")
        picked += by_tc[tc][:PER_TC]
    if len(by_tc) < 2:
        raise SystemExit("flags found for fewer than two time controls")
    picked.sort(key=lambda p: _order("show", f"{p['game']}:{p['flag']['ply']}"))
    for i, p in enumerate(picked, 1):
        p["id"] = f"hc3-{i:02d}"
    return picked


def make() -> Path:
    path = key_path()
    if path.exists():
        key = json.loads(path.read_text())
    else:
        items = sample(read_scan())
        key = {"version": VERSION, "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
               "gate": f"real >= {GATE} of {len(items)}", "items": items}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(key, indent=1) + "\n")
    cards = [card(it) for it in key["items"]]
    out = page_path()
    out.write_text(PAGE.replace("__CARDS__", "\n".join(cards)).replace("__TOTAL__", str(len(cards)))
                   .replace("__KEY__", f"handcheck_m3_v{VERSION}_{key['created_at']}"))
    return out


# --- the page ---------------------------------------------------------------------------------------------------------------

def buttons(item: str, q: str) -> str:
    labels = {"yes": "Yes", "no": "No", "cant": "Can't tell"}
    return (f'<div class="btns" data-item="{item}" data-q="{q}">'
            + "".join(f'<button data-v="{v}">{labels[v]}</button>' for v in ANSWERS) + "</div>")


def passed_board(board: chess.Board) -> chess.Board:
    p = board.copy(stack=False)
    p.push(chess.Move.null())
    return p


def card(it: dict) -> str:
    flag = it["flag"]
    e = flag["evidence"]
    board = chess.Board(flag["fen"])
    me = board.turn
    played = chess.Move.from_uci(flag["move"])
    threat = chess.Move.from_uci(e["threat_move"]["uci"])
    best = chess.Move.from_uci(e["best_move"]["uci"])
    pb = passed_board(board)
    line = e["threat_line"]["uci"]
    arrows = [chess.svg.Arrow(played.from_square, played.to_square, color=RED),
              chess.svg.Arrow(best.from_square, best.to_square, color=GREEN)]
    boards = (f'<figure>{board_svg(board, me, arrows, {})}<figcaption>Your move (you were {side(me)})</figcaption></figure>'
              f'<figure>{board_svg(pb, me, [chess.svg.Arrow(threat.from_square, threat.to_square, color=ORANGE)], {})}'
              f'<figcaption>The same board if you skipped your turn</figcaption></figure>')
    story = (f"You played <b>{html.escape(plain(board, played.uci()))}</b> (red). Their move in the second board "
             f"(orange): <b>{html.escape(plain(pb, threat.uci()))}</b>. The engine's line: "
             f"{html.escape(line_words(pb, line, me))}.")
    qa = (f'<div class="q" data-qid="A"><p><b>A.</b> Look at the second board, as if you had skipped your turn. Could they play '
          f'{html.escape(plain(pb, threat.uci()))} (orange) and come out ahead, by winning material or giving checkmate? '
          f'Count what you could take back.</p>{buttons(it["id"], "A")}</div>'
          f'<div class="q" data-qid="B"><p><b>B.</b> After the move you actually played (red), can they still do it?</p>'
          f'{buttons(it["id"], "B")}</div>'
          f'<div class="q" data-qid="C"><p><b>C.</b> Could you have stopped it with another move, for example '
          f'{html.escape(plain(board, best.uci()))} (green), without losing as much?</p>{buttons(it["id"], "C")}</div>')
    return (f'<section class="card" id="{it["id"]}"><h2>{it["id"]}</h2><div class="boards">{boards}</div>'
            f'<p class="show">{story}</p>{qa}</section>')


def parse_answers(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"^(hc3-\d+):\s*(.+)$", text, re.MULTILINE):
        out[m.group(1)] = dict(re.findall(r"\b([ABC])\s+(yes|no|cant|-)\b", m.group(2)))
    return out


def is_real(a: dict[str, str]) -> bool:
    return all(a.get(q) == "yes" for q in QUESTIONS)


def unanswered(a: dict[str, str]) -> bool:
    """A question was needed but not answered: A always; B only after yes on A; C only after yes on A and B."""
    for q in QUESTIONS:
        if a.get(q) in (None, "-"):
            return True
        if a[q] != "yes":
            return False
    return False


def score(answers_text: str) -> dict:
    key = json.loads(key_path().read_text())
    answers = parse_answers(answers_text)
    items, real, missing = [], 0, []
    for it in key["items"]:
        a = answers.get(it["id"], {})
        if unanswered(a):
            missing.append(it["id"])
        ok = is_real(a)
        real += ok
        e = it["flag"]["evidence"]
        items.append({"id": it["id"], "time_control": it["time_control"], "answers": a, "real": ok,
                      "kind": e.get("threat_kind"), "origin": e.get("threat_origin"), "eval_loss": e.get("eval_loss"),
                      "threat_size_cp": e.get("threat_size_cp"), "also_m1": it["flag"].get("also_m1")})
    by_tc = {}
    for tc in sorted({i["time_control"] for i in items}):
        rows = [i for i in items if i["time_control"] == tc]
        by_tc[tc] = {"real": sum(i["real"] for i in rows), "of": len(rows)}
    result = {"version": VERSION, "scored_at": datetime.now(UTC).isoformat(timespec="seconds"), "real": real, "of": len(items),
              "gate": GATE, "passed": real >= GATE, "by_time_control": by_tc, "unanswered": missing,
              "not_real": [i for i in items if not i["real"]], "items": items}
    key_path().with_name(f"handcheck_m3_v{VERSION}_result.json").write_text(json.dumps(result, indent=1) + "\n")
    return result


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Threat Check</title><style>
:root{color-scheme:light dark;--bg:#fff;--fg:#1c1c1c;--card:#f5f5f2;--line:#d8d8d0;--accent:#2f6f4f}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--card:#222;--line:#444;--accent:#6fbf8f}}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.45 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:18px 0}
h1{font-size:22px} h2{font-size:18px;margin:0 0 .5em}
.boards{display:flex;gap:10px;flex-wrap:wrap}figure{margin:0;flex:1;min-width:200px;max-width:300px}
figure svg{width:100%;height:auto}figcaption{opacity:.7;font-size:.9em}
.show{background:rgba(120,120,120,.12);padding:8px 10px;border-radius:8px}
.q p{margin:.8em 0 .4em}.btns{display:flex;gap:8px;flex-wrap:wrap}
button{font:inherit;padding:10px 18px;border:2px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg);cursor:pointer}
button.on{background:var(--accent);border-color:var(--accent);color:#fff}
#bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:5}
#out{width:100%;height:200px;font:14px monospace}.note{opacity:.85}
.key b{padding:0 4px;border-radius:4px;color:#fff}.r{background:#d9534f}.o{background:#e08e0b}.g{background:#3c9a5f}
.btns button{flex:1;min-width:90px;padding:16px 10px;font-size:19px}
button kbd{opacity:.6;font:12px monospace;margin-left:6px}
.nav{display:flex;gap:8px;margin-top:12px}.nav button{flex:1;padding:10px}
.hide{display:none}.chip{display:inline-block;margin:0 6px 0 0;padding:2px 8px;border-radius:12px;background:rgba(120,120,120,.2);font-size:.85em}
details.help{margin:8px 0}.q.active{outline:2px solid var(--accent);border-radius:10px;padding:2px 10px}
</style></head><body><main>
<div id="bar"><b id="prog">0 of __TOTAL__ answered</b></div>
<div id="intro"><h1>Did you miss a threat?</h1>
<p class="note">30 moves from your older games. For each: look at the two boards and answer up to three quick questions.
<b>Keyboard: Y = yes, N = no, C = can't tell, ← = back.</b> Or tap. It moves on by itself. "Can't tell" is fine, nothing is timed,
and your answers are saved in this browser.</p>
<details class="help"><summary>What do the arrows mean?</summary>
<p class="note key"><b class="r">red</b> the move you played · <b class="g">green</b> a move that stops the threat ·
<b class="o">orange</b> their threatening move. The right-hand board is the same position as if you had skipped your turn.
"Come out ahead" counts everything taken by both sides. None of these games are in the set of recent games your threat score
will be measured on.</p></details></div>
__CARDS__
<div class="nav"><button id="back">← Back</button><button id="skip">Skip →</button></div>
<section class="card hide" id="done"><h2>All done</h2>
<p>Press the button and paste the text in the chat.</p>
<button id="copy">Copy my answers</button> <button id="dl">Download as a file</button>
<p><textarea id="out" readonly></textarea></p></section>
</main><script>
const KEY='__KEY__', total=__TOTAL__, QS=['A','B','C'], VAL={y:'yes',n:'no',c:'cant'};
let ans={}; try{ans=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const cards=[...document.querySelectorAll('.card[id^="hc3-"]')], items=cards.map(c=>c.id);
let pos=0;
function needed(a){const n=['A'];if(a.A==='yes'){n.push('B');if(a.B==='yes')n.push('C')}return n}
function active(a){return needed(a).find(q=>!a[q])||null}
function complete(a){return active(a)===null}
function save(){try{localStorage.setItem(KEY,JSON.stringify(ans))}catch(e){}}
function set(i,q,v){const a=(ans[i]=ans[i]||{});a[q]=v;const n=needed(a);for(const x of QS){if(!n.includes(x))delete a[x]}save();
 paint();if(complete(a)){setTimeout(()=>{if(pos<items.length&&items[pos]===i){pos++;paint();window.scrollTo(0,0)}},250)}}
function paint(){
 const cur=pos<items.length;
 cards.forEach((c,i)=>c.classList.toggle('hide',i!==pos));
 document.getElementById('done').classList.toggle('hide',cur);document.getElementById('intro').classList.toggle('hide',pos>0||Object.keys(ans).length>0);
 if(cur){const a=ans[items[pos]]||{},n=needed(a),act=active(a);
  cards[pos].querySelectorAll('.q').forEach(q=>{const id=q.dataset.qid;q.classList.toggle('hide',!n.includes(id));q.classList.toggle('active',id===act);
   q.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.v===a[id]))})}
 const done=items.filter(i=>complete(ans[i]||{})).length;
 document.getElementById('prog').textContent=(cur?'Position '+(pos+1)+' of '+total+' · ':'')+done+' of '+total+' answered';
 document.getElementById('out').value=items.filter(i=>ans[i]).map(i=>i+': '+QS.map(q=>q+' '+((ans[i]||{})[q]||'-')).join(', ')).join('\\n');
 document.getElementById('back').disabled=pos===0;document.getElementById('skip').disabled=!cur;
}
document.querySelectorAll('.btns button').forEach(x=>x.onclick=()=>{const b=x.parentElement;if(items[pos]===b.dataset.item)set(b.dataset.item,b.dataset.q,x.dataset.v)});
document.addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA'||e.metaKey||e.ctrlKey||e.altKey)return;const k=e.key.toLowerCase();
 if(VAL[k]&&pos<items.length){const a=ans[items[pos]]||{},q=active(a)||needed(a).slice(-1)[0];set(items[pos],q,VAL[k]);e.preventDefault()}
 else if(k==='arrowleft'||k==='b'){if(pos>0){pos--;paint()}e.preventDefault()}
 else if(k==='arrowright'||k==='s'){if(pos<items.length){pos++;paint()}e.preventDefault()}});
document.getElementById('back').onclick=()=>{if(pos>0){pos--;paint()}};
document.getElementById('skip').onclick=()=>{if(pos<items.length){pos++;paint()}};
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.select();
 try{navigator.clipboard.writeText(t.value)}catch(e){document.execCommand('copy')}};
document.getElementById('dl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([document.getElementById('out').value]));a.download='my_threat_check.txt';a.click()};
const first=items.findIndex(i=>!complete(ans[i]||{}));pos=first<0?items.length:first;paint();
</script></body></html>"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.learner.handcheck_m3")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--db", type=Path, default=None, help="store to use (default: the real one; use a copy to leave it alone)")
    s.add_argument("--workers", type=int, default=4)
    sub.add_parser("make")
    sc = sub.add_parser("score")
    sc.add_argument("answers", type=Path)
    args = p.parse_args(argv)
    if args.cmd == "scan":
        print(json.dumps(scan(args.db or default_path(), args.workers), indent=1))
    elif args.cmd == "make":
        print(make())
    else:
        r = score(args.answers.read_text())
        print(json.dumps({k: r[k] for k in ("real", "of", "gate", "passed", "by_time_control", "unanswered")}, indent=1))
        for i in r["not_real"]:
            print(f"  not real: {i['id']} {i['time_control']} kind={i['kind']} origin={i['origin']} answers={i['answers']} "
                  f"loss={i['eval_loss']} threat={i['threat_size_cp']} also_m1={i['also_m1']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
