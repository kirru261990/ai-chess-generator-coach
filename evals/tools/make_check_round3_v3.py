"""Round 3 of the owner's check of `missed_threat_v3` (LABEL_RULE.md Amendment 3). Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/make_check_round3_v3.py

Draws 24 frozen items the owner has not seen (8 missed, 8 met, 8 not_applicable), and for each one draws the opponent's best move after a
pass in BLUE (for every item, so the arrow does not reveal the label). The owner is asked whether that blue move wins material. This checks
the labels, not the owner's eye for threats (rounds 1 and 2 showed it missed some). Writes check_page_r3.html and check_key_r3.json
(git-ignored). The set files are frozen and are only read.
"""

import html
import json
import random
import sys
from pathlib import Path

import chess
import chess.svg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_missed_threat_set as V
import build_missed_threat_set_v3 as V3
from build_real_play_set import Engine
from make_handcheck_page import plain_move, side

SET = V.ROOT / "evals" / "sets" / "missed_threat_v3"
SEED = 20261031
PER = {"missed": 8, "met": 8, "not_applicable": 8}


def card(n, total, r, blue):
    board = chess.Board(r["fen"])
    move = chess.Move.from_uci(r["move_uci"])
    X, Y = side(board.turn), side(not board.turn)
    p = V.passed(board)
    arrows = [chess.svg.Arrow(move.from_square, move.to_square, color="#d9534fcc"),
              chess.svg.Arrow(blue.from_square, blue.to_square, color="#2a6fdbcc")]
    svg = chess.svg.board(board, orientation=board.turn, size=340, arrows=arrows)
    qs = {"A": f"Imagine {X} does nothing this turn. Then {Y} plays the BLUE move. Does {Y} win 2 or more points once everyone has taken back, or checkmate? (Pawn 1, knight or bishop 3, rook 5, queen 9. 1 pawn up does not count.)",
          "B": f"{X} plays the real move (RED) instead. Can {Y} still win that much with the blue move, or something like it?",
          "C": f"Was there a {X} move that stops it?"}
    return (f'<section class="card" data-id="{r["id"]}" data-q="{html.escape(json.dumps(qs))}" hidden><p class="n">{n} of {total}</p>'
            f'<div class="board">{svg}</div><p class="mv">Red = the move {X} played: {html.escape(plain_move(board, move))}<br>'
            f'Blue = {Y}\'s move if {X} did nothing: {html.escape(plain_move(p, blue))}</p></section>')


def main(set_name="missed_threat_v3", seed=SEED, round_no=3):
    global SET
    SET = V.ROOT / "evals" / "sets" / set_name
    src = "positions.jsonl" if (SET / "positions.jsonl").exists() else "candidates.jsonl"  # a set not yet frozen is read from its candidates
    items = [json.loads(x) for x in (SET / src).read_text().splitlines()]
    seen = set()
    if set_name == "missed_threat_v3":  # exclude what the owner saw in rounds 1 and 2 (ids from the committed answers file; the key is git-ignored)
        seen = {(x["fen"], x["move_uci"]) for x in json.loads((SET / "check_round1_items.json").read_text()).values()}
        r2 = [line.split()[0] for line in (SET / "check_round2_answers.txt").read_text().splitlines() if line.strip()]
        cands = {x["id"]: x for x in map(json.loads, (SET / "candidates.jsonl").read_text().splitlines())}
        seen |= {(cands[i]["fen"], cands[i]["move_uci"]) for i in r2}
    rng = random.Random(seed)
    sample = []
    for label, k in PER.items():
        pool = [r for r in items if r["label"] == label and (r["fen"], r["move_uci"]) not in seen]
        sample += rng.sample(pool, k)
    rng.shuffle(sample)
    blues = {}
    with Engine() as engine:
        for r in sample:
            p = V.passed(chess.Board(r["fen"]))
            pv = engine.analyse(p, V.ORACLE, perspective=p.turn).pv
            blues[r["id"]] = chess.Move.from_uci(pv[0])
    page = V3.PAGE.replace("@@CARDS@@", "".join(card(i, len(sample), r, blues[r["id"]]) for i, r in enumerate(sample, 1)))
    page = page.replace("m3v3check_r2", f"m3check_{set_name}_r{round_no}")
    (SET / f"check_page_r{round_no}.html").write_text(page)
    (SET / f"check_key_r{round_no}.json").write_text(json.dumps({r["id"]: r["label"] for r in sample}, indent=1) + "\n")
    print(len(sample), {k: sum(r["label"] == k for r in sample) for k in PER})


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], int(a[1]), int(a[2])) if len(a) == 3 else main()
