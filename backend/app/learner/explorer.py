"""A local page that shows what Steps 1a and 1b built and found (PRD v2; ADR 0006).

  uv run python -m app.learner.explorer [--per-type 3]    # writes data/evidence/explorer.html (git-ignored)

The page holds the owner's games, so it is written under `data/` and never committed or published.

What it shows:
- Step 1a: the games and their pools, the pinned engine config, the cache size, the rules the database enforces.
- Step 1b: the funnel from the owner's moves to stored positions, with the reasons candidates were set aside.
- A few example positions per type, **from the PRACTICE pool only**. Held-out positions appear only as counts: seeing one
  would spoil it as an unseen test (PRD §5.3). The examples shown, and any other row for the same board (`seen.py`), are
  marked `excluded_reason = 'shown_in_explorer'`, so
  practice sessions can skip them (the owner has seen the answer) and they are never chosen again for this page.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys

import chess
import chess.svg

from app import config
from app.db.schema import connect
from app.learner import seen

SHOWN = "shown_in_explorer"
NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen",
         chess.KING: "king"}
RED, ORANGE, GREEN, TARGET = "#d9534fcc", "#f0ad4ecc", "#3c9a5fcc", "#ffd54f99"

REASONS = {  # plain words for the runner's reason codes
    "decided": "the game was already decided (one side far ahead)",
    "before_min_ply": "still in the opening (before move 5)",
    "only_legal_move": "there was only one legal move",
    "loss_below_threshold": "the move did not cost enough to count",
    "material_swing_below_minimum": "the piece could be taken, but not for a real gain (it was traded back)",
    "top_line_not_a_capture_of_player_piece": "the engine's punishment was something else, not taking a piece",
    "no_sound_move": "the piece was lost whatever was played",
    "loss_not_stable": "the engine changed its mind at a shallower search",
    "no_free_capture_in_best_lines": "no free piece among the engine's best moves",
    "played_a_free_capture": "you took the free piece (well done)",
    "move_not_sound_enough": "your move there was not quite good enough",
    "best_line_wins_material": "there was something to win after all",
    "all_checks_hold": "confirmed",
}


def side(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def plain(board: chess.Board, uci: str) -> str:
    """'your knight takes the pawn on c2' in plain words (no notation)."""
    move = chess.Move.from_uci(uci)
    piece = board.piece_at(move.from_square)
    if board.is_castling(move):
        return "castle"
    victim = board.piece_at(move.to_square)
    to = chess.square_name(move.to_square)
    text = f"{NAMES[piece.piece_type]} takes the {NAMES[victim.piece_type]} on {to}" if victim else \
        f"{NAMES[piece.piece_type]} to {to}"
    if move.promotion:
        text += f", becoming a {NAMES[move.promotion]}"
    return text


def pawns(cp: int) -> str:
    return "more than 10 pawns" if cp >= 1000 else f"about {cp / 100:.1f} pawns"


def board_svg(board: chess.Board, orientation: chess.Color, arrows, fill) -> str:
    return chess.svg.board(board, orientation=orientation, size=340, arrows=arrows, fill=fill, coordinates=True)


def mistake_card(row, evidence: dict) -> str:
    board = chess.Board(evidence["fen"])
    me = board.turn
    played = chess.Move.from_uci(evidence["player_move"]["uci"])
    after = board.copy(stack=False)
    after.push(played)
    line = evidence["refutation_line"]["uci"]
    alts = json.loads(row["verified_alternatives_json"] or "[]")
    fill = {chess.parse_square(sq): TARGET for sq in evidence["target_squares"]}
    arrows = [chess.svg.Arrow(played.from_square, played.to_square, color=RED)]
    if evidence["mistake_type"] == "M1":
        reply = chess.Move.from_uci(line[0])
        lost = evidence["lost_piece_square_after"]
        title = "Hanging piece"
        if evidence["lost_piece"] == "moved":
            what = (f"You moved your {NAMES[board.piece_at(played.from_square).piece_type]} to "
                    f"{chess.square_name(played.to_square)}, where it could be taken.")
        else:
            what = (f"Your {NAMES[after.piece_at(chess.parse_square(lost)).piece_type]} on {lost} could be taken, "
                    f"and you played {plain(board, played.uci())}.")
        then = f"{side(not me)} replied: {plain(after, reply.uci())}."
        board_after = after
        board_after_arrows = [chess.svg.Arrow(reply.from_square, reply.to_square, color=ORANGE)]
    else:
        capture = chess.Move.from_uci(line[0])
        title = "Missed free capture"
        what = (f"{side(not me)}'s {NAMES[board.piece_at(capture.to_square).piece_type]} on "
                f"{chess.square_name(capture.to_square)} was free to take ({plain(board, capture.uci())}). "
                f"You played {plain(board, played.uci())} instead.")
        then = ""
        board_after = None
        arrows.append(chess.svg.Arrow(capture.from_square, capture.to_square, color=GREEN))
    better = ", ".join(plain(board, a["uci"]) for a in alts)
    boards = f'<figure>{board_svg(board, me, arrows, fill)}<figcaption>The position you faced</figcaption></figure>'
    if board_after is not None:
        boards += (f'<figure>{board_svg(board_after, me, board_after_arrows, {})}'
                   f'<figcaption>After your move</figcaption></figure>')
    return (f'<article class="card"><h4>{title} <span class="meta">move {evidence["ply"] // 2 + 1}, you were '
            f'{side(me)}</span></h4><div class="boards">{boards}</div>'
            f'<p>{html.escape(what)} {html.escape(then)}</p>'
            f'<p class="cost">It cost {pawns(evidence["eval_loss"])} of advantage '
            f'(the engine checked this twice, at two depths).</p>'
            f'<p class="better">Good moves here: {html.escape(better)}.</p>'
            f'<p class="legend"><b class="r">red</b> your move · <b class="o">orange</b> the reply · '
            f'<b class="g">green</b> the free capture · <b class="y">yellow</b> the piece that mattered</p></article>')


def clean_card(evidence: dict) -> str:
    board = chess.Board(evidence["fen"])
    me = board.turn
    played = chess.Move.from_uci(evidence["player_move"]["uci"])
    fill = {chess.parse_square(sq): TARGET for sq in evidence["attacked_squares"]}
    svg = board_svg(board, me, [chess.svg.Arrow(played.from_square, played.to_square, color=GREEN)], fill)
    attacked = ", ".join(evidence["attacked_squares"])
    return (f'<article class="card"><h4>Nothing in danger <span class="meta">move {evidence["ply"] // 2 + 1}, you were '
            f'{side(me)}</span></h4><div class="boards"><figure>{svg}<figcaption>The position you faced</figcaption>'
            f'</figure></div><p>Pieces were attacked ({html.escape(attacked)}, in yellow) but nothing could be won or lost. '
            f'You played {html.escape(plain(board, played.uci()))} (green), a good move. In a test, the right answer '
            f'here is "No immediate threat".</p></article>')


def pick_examples(conn, per_type: int) -> dict[str, list]:
    """Examples from the PRACTICE pool only: boards already shown first, then unseen boards in a fixed pseudo-random order.

    A board seen anywhere (any of its rows marked) is never a fresh example (`seen.UNSEEN_BOARD`).
    """
    seen.propagate(conn)
    out = {}
    for key, where in (("M1", "kind = 'MISTAKE' AND mistake_type = 'M1'"),
                       ("M2", "kind = 'MISTAKE' AND mistake_type = 'M2'"), ("CLEAN", "kind = 'CLEAN'")):
        rows = conn.execute(f"SELECT * FROM position WHERE pool = 'PRACTICE' AND {where}").fetchall()
        shown = [r for r in rows if r["excluded_reason"] == SHOWN]
        unseen = {r["id"] for r in conn.execute(f"SELECT id FROM position WHERE {seen.UNSEEN_BOARD}")}
        fresh = sorted((r for r in rows if r["excluded_reason"] is None and r["id"] in unseen),
                       key=lambda r: hashlib.sha256(f"explorer:{r['id']}".encode()).hexdigest())
        out[key] = (shown + fresh)[:per_type]
    return out


def latest_run() -> dict | None:
    runs = sorted((config.DATA_DIR / "evidence").glob("run_*.json"))
    return json.loads(runs[-1].read_text()) if runs else None


def funnel_rows(run: dict, kind: str, label: str) -> str:
    reasons = {k.split(":", 1)[1]: v for k, v in run["reasons"].items() if k.startswith(kind + ":")}
    total = sum(reasons.values())
    rows = []
    for key, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        outcome, reason = key.split(":")
        kept = outcome in {"mistake", "missed", "clean"}
        width = round(100 * n / total) if total else 0
        rows.append(f'<tr class="{"kept" if kept else ""}"><td>{html.escape(REASONS.get(reason, reason))}</td>'
                    f'<td class="n">{n}</td><td class="bar"><span style="width:{width}%"></span></td></tr>')
    return f'<h4>{label}: {total} checked</h4><table class="funnel">{"".join(rows)}</table>'


def build(conn, per_type: int) -> str:
    games = {(r["time_control"], r["pool"]): r["n"] for r in
             conn.execute("SELECT time_control, pool, COUNT(*) AS n FROM game GROUP BY time_control, pool")}
    positions = {(r["k"], r["pool"]): r["n"] for r in conn.execute(
        "SELECT kind || IFNULL(':' || mistake_type, '') AS k, pool, COUNT(*) AS n FROM position GROUP BY k, pool")}
    cfg = conn.execute("SELECT * FROM engine_config ORDER BY depth DESC LIMIT 1").fetchone()
    cached = conn.execute("SELECT COUNT(*) FROM engine_analysis").fetchone()[0]
    run = latest_run()
    examples = pick_examples(conn, per_type)
    for rows in examples.values():
        for r in rows:
            seen.mark_seen(conn, r["id"], SHOWN)

    def g(tc, pool):
        return games.get((tc, pool), 0)

    def p(k, pool):
        return positions.get((k, pool), 0)

    tcs = (("600", "10 minute"), ("900+10", "15 + 10"))
    pool_rows = "".join(
        f'<tr><td>{label}</td><td class="n">{g(tc, "PRACTICE")}</td><td class="n">{g(tc, "HELDOUT")}</td>'
        f'<td class="split"><span class="pr" style="flex:{g(tc, "PRACTICE")}"></span>'
        f'<span class="ho" style="flex:{g(tc, "HELDOUT")}"></span></td></tr>' for tc, label in tcs)
    pos_rows = "".join(
        f'<tr><td>{label}</td><td class="n">{p(k, "PRACTICE")}</td><td class="n">{p(k, "HELDOUT")}</td>'
        f'<td class="n">{need}</td><td>{"✅" if p(k, "HELDOUT") >= need else "❌"}</td></tr>'
        for k, label, need in (("MISTAKE:M1", "Hanging piece (M1)", 16), ("MISTAKE:M2", "Missed free capture (M2)", 16),
                               ("CLEAN", "Nothing in danger (clean)", 16)))
    funnel = ""
    if run:
        funnel = (funnel_rows(run, "M1", "Hanging piece") + funnel_rows(run, "M2", "Missed free capture")
                  + funnel_rows(run, "CLEAN", "Nothing in danger"))
    cards = {k: "".join(clean_card(json.loads(r["evidence_json"])) if k == "CLEAN" else
                        mistake_card(r, json.loads(r["evidence_json"])) for r in rows) for k, rows in examples.items()}
    rules = [
        "A game is put in Practice or Test once, and never moves.",
        "A position belongs to the same pool as its game.",
        "Practice can never use a test position; a test can never use a practice position.",
        "A test position is used in one test only, ever.",
        "Only one unfinished test per mistake type at a time.",
        "A test answer is capped at 5 minutes.",
        "A frozen 'before' window can never be edited or deleted.",
    ]
    engine = (f"{cfg['version']}, network {cfg['network']}, depth {cfg['depth']} (checked again at depth "
              f"{cfg['depth'] - 4}), top {cfg['multipv']} moves, {cfg['threads']} thread, {cfg['hash_mb']} MB memory, "
              f"fingerprint {cfg['binary_sha256'][:12]}…") if cfg else "not run yet"
    return PAGE.format(
        pool_rows=pool_rows, pos_rows=pos_rows, engine=html.escape(engine), cached=cached,
        rules="".join(f"<li>{html.escape(r)}</li>" for r in rules), funnel=funnel,
        minutes=run["minutes"] if run else "?", m1=cards["M1"], m2=cards["M2"], clean=cards["CLEAN"],
    )


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Mistake Finder</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1f2328;--muted:#656d76;--card:#fff;--line:#d8dee4;--pr:#3c7dd9;--ho:#c46a1b;--ok:#3c9a5f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e6e6e6;--muted:#9aa4ae;--card:#1f2228;--line:#30363d}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:1080px;margin:auto;padding:24px 16px 64px}}
h1{{margin:.2em 0}}h2{{margin-top:2em;border-bottom:1px solid var(--line);padding-bottom:.3em}}
.lead,.meta,figcaption,.legend{{color:var(--muted)}}.meta{{font-weight:400;font-size:.85em}}
table{{border-collapse:collapse;margin:.5em 0 1em;width:100%;max-width:640px}}
td,th{{padding:.35em .5em;border-bottom:1px solid var(--line);text-align:left}}td.n{{text-align:right;width:4em}}
.split{{display:flex;width:220px;height:14px;border-radius:7px;overflow:hidden;padding:0;margin-top:.5em}}
.split .pr{{background:var(--pr)}}.split .ho{{background:var(--ho)}}
.key b{{display:inline-block;width:12px;height:12px;border-radius:3px;margin:0 4px -1px 10px}}
.funnel td.bar{{width:40%}}.funnel .bar span{{display:block;height:10px;background:var(--muted);border-radius:5px}}
.funnel tr.kept td{{font-weight:600}}.funnel tr.kept .bar span{{background:var(--ok)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.card h4{{margin:.2em 0 .5em}}.boards{{display:flex;gap:8px;flex-wrap:wrap}}figure{{margin:0;flex:1;min-width:150px}}
figure svg{{width:100%;height:auto}}.cost{{font-weight:600}}.legend{{font-size:.8em}}
.r{{color:#d9534f}}.o{{color:#e08e0b}}.g{{color:#3c9a5f}}.y{{color:#c9a400}}
.note{{background:var(--card);border-left:4px solid var(--ho);padding:.6em 1em;border-radius:6px}}
</style></head><body><main>
<h1>What the mistake finder built and found</h1>
<p class="lead">Steps 1a and 1b of the plan, on your own Chess.com games. Nothing here is a practice screen yet; this shows the
foundation those screens will use.</p>

<h2>Step 1a · The foundation</h2>
<h3>1. Your games, split once and for all</h3>
<p>Every game goes into <b style="color:var(--pr)">Practice</b> (you will replay its mistakes) or
<b style="color:var(--ho)">Test</b> (kept hidden, to check later whether you learned). The split comes from the game's ID, so
it never changes.</p>
<table><tr><th>Time control</th><th class="n">Practice</th><th class="n">Test</th><th></th></tr>{pool_rows}</table>
<h3>2. One fixed engine</h3>
<p>{engine}. It refuses to run if the engine is any other build, so every result can be repeated. Positions analysed and
stored so far: <b>{cached}</b> (never analysed twice).</p>
<h3>3. Rules the database itself enforces</h3>
<p>Even buggy code cannot break these; each one has a test.</p><ul>{rules}</ul>

<h2>Step 1b · What it found</h2>
<p>The run took {minutes} minutes. Each candidate move is checked against the plan's strict rules; anything in doubt is set
aside rather than guessed (rows in <b>bold</b> are kept).</p>
{funnel}
<h3>Positions stored</h3>
<table><tr><th>Type</th><th class="n">Practice</th><th class="n">Test</th><th class="n">Test needs</th><th></th></tr>
{pos_rows}</table>
<p class="note"><b>Why you only see Practice positions below.</b> A test position only measures learning if you have never
seen it. The examples below come from the Practice pool, and they are now marked as "already seen" so practice sessions can
skip them.</p>

<h2>Examples from your games</h2>
<h3>Hanging piece</h3><div class="cards">{m1}</div>
<h3>Missed free capture</h3><div class="cards">{m2}</div>
<h3>Nothing in danger (the "No immediate threat" answer)</h3><div class="cards">{clean}</div>
</main></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.learner.explorer")
    p.add_argument("--per-type", type=int, default=3)
    args = p.parse_args(argv)
    conn = connect()
    out = config.DATA_DIR / "evidence" / "explorer.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(conn, args.per_type))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
