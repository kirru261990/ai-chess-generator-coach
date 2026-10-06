"""Build evals/sets/real_play_v1 following evals/sets/real_play_v1/LABEL_RULE.md (v0.2).

Independence rule: this file imports NOTHING from app/detectors/. It uses python-chess, the
engine wrapper (to run Stockfish) and one ranking helper from the review module.

Run from the repo root:  cd backend && uv run python ../evals/tools/build_real_play_set.py
Outputs (in evals/sets/real_play_v1/): positions.jsonl, provenance.json,
handcheck_owner.md, handcheck_second.md (labels hidden). No detector is run.
"""

import csv
import hashlib
import io
import json
import random
import sys
from pathlib import Path

import chess
import zstandard

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.stockfish import Budget, Engine
from app.learner.review import cp_equiv

SEED = 20261007
PUZZLES = ROOT / "data" / "lichess" / "lichess_db_puzzle.csv.zst"
OUT = ROOT / "evals" / "sets" / "real_play_v1"
ORACLE = Budget(depth=14)  # LABEL_RULE decision 2
MISS_LOSS_CP = 300  # LABEL_RULE decision 2: engine loss that confirms a miss
UNCERTAIN_LOSS_CP = 100  # below this the engine does not confirm a loss: the right outcome is `uncertain`
BANDS = (400, 600, 800, 1000)
PER_BAND = 10
NA_TARGET = 20
PV_PLIES = 6
EXCLUDED_THEMES = {"sacrifice", "attraction", "deflection", "intermezzo", "quietMove", "clearance", "zugzwang"}
# Piece values for the material count (own copy: nothing is imported from app/detectors).
VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def balance(board: chess.Board, color: chess.Color) -> int:
    return sum(VAL[p.piece_type] * (1 if p.color == color else -1)
               for p in board.piece_map().values() if p.piece_type != chess.KING)


def is_plain_nonpawn_capture(board: chess.Board, move: chess.Move) -> bool:
    victim = board.piece_at(move.to_square)
    return (board.is_capture(move) and not board.is_en_passant(move) and move.promotion is None
            and victim is not None and victim.piece_type not in (chess.PAWN, chess.KING))


MIN_GAIN = 2  # pawns of net material that count as "winning a piece" (LABEL_RULE section 1)


def exchange(board, square):
    """Best net material the side to move can win by capturing on `square`: a full search over
    every legal capture and recapture in any order, stopping is always allowed (so >= 0).
    Written separately from the detectors' exchange code (which takes the cheapest attacker
    first), so agreement between them is evidence, not an echo."""
    best = 0
    for m in list(board.legal_moves):
        if m.to_square != square or not board.is_capture(m) or board.is_en_passant(m) or m.promotion:
            continue
        gain = VAL[board.piece_at(square).piece_type]
        board.push(m)
        best = max(best, gain - exchange(board, square))
        board.pop()
    return best


def capture_net(board, move):
    """Net material the side to move gets from this one capture of a non-pawn piece, after the
    opponent's best recaptures; 0 if it is not such a capture."""
    if not is_plain_nonpawn_capture(board, move):
        return 0
    gain = VAL[board.piece_at(move.to_square).piece_type]
    board.push(move)
    net = gain - exchange(board, move.to_square)
    board.pop()
    return net


def best_capture_net(board):
    """The most the side to move can win by capturing a non-pawn piece (0 if nothing pays)."""
    return max([0] + [capture_net(board, m) for m in list(board.legal_moves)])


def choice_flags(board):
    """For each legal move: does it leave a non-pawn piece to be won (net >= MIN_GAIN)?"""
    return {m: hang_gain_after(board, m) >= MIN_GAIN for m in list(board.legal_moves)}


def engine_loss(engine, board, move):
    """(best_cp, after_cp, loss) from the mover's side at the oracle depth; mates are clamped."""
    mover = board.turn
    best = engine.analyse(board, ORACLE, perspective=mover)
    after = board.copy()
    after.push(move)
    a = engine.analyse(after, ORACLE, perspective=mover)
    b = cp_equiv(best.score.cp, best.score.mate, best.score.mate_sign)
    c = cp_equiv(a.score.cp, a.score.mate, a.score.mate_sign)
    return b, c, b - c


def hang_gain_after(board, move):
    """After `move`, the most the opponent can win by capturing one of the mover's non-pawn pieces."""
    after = board.copy()
    after.push(move)
    return best_capture_net(after)


def load_puzzles():
    """Yield dicts for every puzzle in the file with its themes, rating and moves parsed."""
    with PUZZLES.open("rb") as f, zstandard.ZstdDecompressor().stream_reader(f) as r:
        for row in csv.DictReader(io.TextIOWrapper(r, encoding="utf-8")):
            rating = int(row["Rating"])
            if not 400 <= rating <= 1199:
                continue
            moves = row["Moves"].split()
            if len(moves) >= 2:
                yield {"id": row["PuzzleId"], "fen": row["FEN"], "moves": moves, "rating": rating,
                       "band": (rating // 200) * 200, "themes": row["Themes"].split()}


def prepare(p):
    """Replay the opening of a puzzle; return None if it is not usable."""
    try:
        before = chess.Board(p["fen"])
        m0 = chess.Move.from_uci(p["moves"][0])
        if m0 not in before.legal_moves:
            return None
        after = before.copy()
        after.push(m0)
        m1 = chess.Move.from_uci(p["moves"][1])
        if m1 not in after.legal_moves:
            return None
    except ValueError:
        return None
    return {**p, "before": before, "m0": m0, "after": after, "m1": m1,
            "mate_theme": any(t.startswith("mate") or t.endswith("Mate") for t in p["themes"])}


def item(det, label, board, move, p, category, material_label=None, **extra):
    """`label` is the outcome a correct detector gives WITH engine evidence. `material_label` is what a
    person can verify from the board alone (the hand-check answers map to it); they differ only when
    the engine overrides the material picture."""
    return {"detector": det, "label": label, "material_label": material_label or label,
            "fen": board.fen(), "move_uci": move.uci(),
            "move_san": board.san(move), "category": category, "constructed": category.startswith("constructed"),
            "puzzle_id": p["id"], "rating": p["rating"], "band": p["band"], "mate_theme": p["mate_theme"],
            "themes": p["themes"], "source_url": f"https://lichess.org/training/{p['id']}", **extra}


def best_line_net(engine, board):
    """Engine's best move and the mover's material change along its line (up to 6 plies)."""
    mover = board.turn
    a = engine.analyse(board, ORACLE, perspective=mover)
    walk, base = board.copy(), balance(board, mover)
    last_even, last = None, base
    for i, u in enumerate(a.pv[:PV_PLIES], 1):
        walk.push_uci(u)
        last = balance(walk, mover)
        if i % 2 == 0:
            last_even = last
    return a, (last_even if last_even is not None else last) - base


def build_real(rng, engine):
    pool = [p for p in (prepare(x) for x in load_puzzles()
                        if "hangingPiece" in x["themes"] and not EXCLUDED_THEMES & set(x["themes"]))
            if p and is_plain_nonpawn_capture(p["after"], p["m1"])]
    seen, uniq = set(), []
    for p in pool:
        if p["id"] not in seen:
            seen.add(p["id"])
            uniq.append(p)
    queues = {b: [p for p in uniq if p["band"] == b] for b in BANDS}
    for q in queues.values():
        rng.shuffle(q)
    items, shortfall = [], {}

    def take(b, ok=lambda p: True):  # one unused puzzle from band b that passes `ok`, never reused
        while queues[b]:
            p = queues[b].pop()
            if ok(p):
                return p
        return None

    # Every real item is confirmed by the independent exchange search, not only by Lichess's theme.
    taken_ok = lambda p: capture_net(p["after"], p["m1"]) >= MIN_GAIN
    def blunder_ok(p):  # it hangs a piece AND a safe alternative existed (else the outcome is n/a)
        flags = choice_flags(p["before"])
        return flags[p["m0"]] and any(not v for m, v in flags.items() if m != p["m0"])

    def safe_ok(p):  # it leaves nothing to win AND some other move would have (else the outcome is n/a)
        flags = choice_flags(p["after"])
        return not flags[p["m1"]] and any(flags.values())

    opportunity_ok = lambda p: best_capture_net(p["after"]) >= MIN_GAIN

    for b in BANDS:
        for _ in range(PER_BAND):  # missed_free taken (real)
            if (p := take(b, taken_ok)):
                items.append(item("missed_free", "taken", p["after"], p["m1"], p, "real_taken"))
        got = 0
        while got < PER_BAND and queues[b]:  # hanging_own: a real move that hung a piece
            p = take(b, blunder_ok)
            if p is None:
                break
            best_cp, after_cp, loss = engine_loss(engine, p["before"], p["m0"])
            ev = {"engine_best_cp": best_cp, "engine_after_cp": after_cp, "loss_cp": loss}
            if loss >= MISS_LOSS_CP:  # the engine confirms a real loss: the outcome is `missed`
                items.append(item("hanging_own", "missed", p["before"], p["m0"], p, "real_blunder", **ev))
            elif loss < UNCERTAIN_LOSS_CP:  # it hangs a piece but the engine does not confirm: `uncertain`
                items.append(item("hanging_own", "uncertain", p["before"], p["m0"], p, "real_blunder",
                                  material_label="missed", **ev))
            else:  # 100-299 cp: neither clearly an error nor clearly not; excluded as ambiguous
                continue
            got += 1
        if got < PER_BAND:
            shortfall[f"hanging_own real_blunder band {b}"] = PER_BAND - got
        for _ in range(PER_BAND):  # hanging_own taken (real, safe solution move)
            if (p := take(b, safe_ok)):
                items.append(item("hanging_own", "taken", p["after"], p["m1"], p, "real_safe"))
        made, tries = 0, 0
        while made < PER_BAND and tries < 400 and queues[b]:  # missed_free missed (constructed)
            p, tries = take(b, opportunity_ok), tries + 1
            if p is None:
                break
            best = engine.analyse(p["after"], ORACLE)
            if best.best_move != p["m1"].uci():
                continue
            alts = [m for m in p["after"].legal_moves if not p["after"].is_capture(m)]
            rng.shuffle(alts)
            for alt in alts[:6]:
                nxt = p["after"].copy()
                nxt.push(alt)
                if nxt.is_game_over():
                    continue
                a = engine.analyse(nxt, ORACLE, perspective=p["after"].turn)
                loss = (cp_equiv(best.score.cp, best.score.mate, best.score.mate_sign)
                        - cp_equiv(a.score.cp, a.score.mate, a.score.mate_sign))
                if loss >= MISS_LOSS_CP:
                    items.append(item("missed_free", "missed", p["after"], alt, p, "constructed_miss", loss_cp=loss))
                    made += 1
                    break
        if made < PER_BAND:
            shortfall[f"missed_free constructed band {b}"] = PER_BAND - made
    return items, {"eligible_pool": len(uniq), **{f"left_band_{b}": len(q) for b, q in queues.items()}}, shortfall


def build_not_applicable(rng):
    """missed_free not_applicable: real positions from non-hangingPiece puzzles in which NO legal
    capture of a non-pawn piece nets MIN_GAIN pawns (by the independent exchange search), although the
    mover could capture a defended non-pawn piece. The excluded themes apply here too."""
    rows = [x for x in load_puzzles()
            if "hangingPiece" not in x["themes"] and not EXCLUDED_THEMES & set(x["themes"])]
    rng.shuffle(rows)
    per = NA_TARGET // len(BANDS)
    per_band, out = {b: 0 for b in BANDS}, []
    for x in rows:
        if all(v >= per for v in per_band.values()):
            break
        if per_band[x["band"]] >= per:
            continue
        p = prepare(x)
        if not p:
            continue
        board = p["before"]  # a real position from a real game, side to move = the blunderer
        if not any(is_plain_nonpawn_capture(board, m) and board.is_attacked_by(not board.turn, m.to_square)
                   for m in board.legal_moves):
            continue
        if best_capture_net(board) >= MIN_GAIN:  # a legal capture wins material: not "no opportunity"
            continue
        out.append(item("missed_free", "not_applicable", board, p["m0"], p, "no_opportunity", exchange_net=0))
        per_band[x["band"]] += 1
    return out, {f"missed_free n/a band {b}": per - n for b, n in per_band.items() if n < per}


# ---- hand-built adversarial positions: (detector, fen, uci, label, reason, facts checked by python-chess)
ADV = [
    ("missed_free", "4rk2/8/8/8/2p5/3n4/4P3/3QK3 w - - 0 1", "e1f1", "not_applicable",
     "The knight on d3 gives check. The e2 pawn that could take it is pinned by Re8, so the only legal capture is Qxd3, which loses the queen to ...cxd3.", {"illegal": ["e2d3"]}),
    ("missed_free", "4k3/8/4p3/3n4/8/8/8/3RR1K1 w - - 0 1", "d1d5", "taken",
     "Rxd5 wins the knight: the e6 pawn that would recapture is pinned to Ke8 by Re1, so ...exd5 is illegal.", {"illegal_after": ["d1d5", "e6d5"]}),
    ("missed_free", "4k3/8/4p3/3n4/8/8/8/3RR1K1 w - - 0 1", "g1f1", "missed",
     "Same position: the knight can be won for free (the recapture is illegal) and this move ignores it.", {}),
    ("missed_free", "4k3/8/4p3/3n4/8/8/8/3R2K1 w - - 0 1", "g1f1", "not_applicable",
     "No pin here, so ...exd5 is legal: Rxd5 would lose a rook for a knight. Nothing is free.", {}),
    ("missed_free", "4k3/8/4p3/3r4/2P5/8/8/3QK3 w - - 0 1", "c4d5", "taken",
     "cxd5 wins the rook; ...exd5 Qxd5 is an even pawn trade.", {}),
    ("missed_free", "4k3/8/4p3/3r4/2P5/8/8/3QK3 w - - 0 1", "d1d5", "missed",
     "Qxd5?? takes the rook but loses the queen to ...exd5. A losing capture is not taking the free piece.", {}),
    ("missed_free", "4k3/8/8/3n4/2P5/8/8/3QK3 w - - 0 1", "d1d5", "taken",
     "Two capturers (pawn and queen) can win the loose knight; either is fine.", {}),
    ("missed_free", "4r1k1/8/8/8/3n4/8/8/3RK3 w - - 0 1", "e1f1", "not_applicable",
     "The knight on d4 is loose but White is in check from Re8, so Rxd4 is illegal: the check must be answered.", {"illegal": ["d1d4"]}),
    ("missed_free", "6k1/5ppp/8/3n4/8/8/8/R2R2K1 w - - 0 1", "a1a8", "uncertain",
     "Ra8 is checkmate, which beats winning the loose knight with Rxd5. With engine evidence the right outcome is uncertain.", {}),
    ("missed_free", "4k3/8/4p3/3r4/8/1B6/8/4K3 w - - 0 1", "b3d5", "taken",
     "Bxd5 exd5 wins a rook for a bishop (two pawns of material): the rook is insufficiently defended.", {}),
    ("missed_free", "4k3/8/4p3/3r4/8/1B6/8/4K3 w - - 0 1", "e1f1", "missed",
     "Same position: the rook can be won for a bishop and this move ignores it.", {}),
    ("missed_free", "4k3/8/4p3/3n4/8/1B6/8/4K3 w - - 0 1", "e1f1", "not_applicable",
     "Bxd5 exd5 is an even trade of minor pieces, so nothing is free.", {}),
    ("missed_free", "4k3/8/8/3p4/8/8/8/3RK3 w - - 0 1", "e1f1", "not_applicable",
     "Only a pawn can be won; pawns are out of scope for this pattern in v1.", {}),
    ("hanging_own", "2k5/8/8/8/2p5/8/3N4/2R1K3 w - - 0 1", "d2b3", "not_applicable",
     "The only piece that could take a knight on b3 is the c4 pawn, which is pinned to Kc8 by Rc1, so nothing can hang.", {"illegal_after": ["d2b3", "c4b3"]}),
    ("hanging_own", "6k1/8/8/8/2p5/8/3N4/2R1K3 w - - 0 1", "d2b3", "missed",
     "Same position without the pin: ...cxb3 wins the knight.", {"legal_after": ["d2b3", "c4b3"]}),
    ("hanging_own", "4k3/8/4p3/8/1NP5/8/8/4K3 w - - 0 1", "b4d5", "missed",
     "Nd5 is attacked by the e6 pawn and defended only by the c4 pawn: ...exd5 cxd5 wins a knight for a pawn.", {}),
    ("hanging_own", "4k3/8/5n2/8/1NP5/8/8/3QK3 w - - 0 1", "b4d5", "taken",
     "Nd5 is attacked by the f6 knight but defended twice; ...Nxd5 cxd5 is an even trade.", {}),
    ("hanging_own", "4k3/8/8/3p4/8/3Q4/8/4K3 w - - 0 1", "d3e4", "missed",
     "Qe4 walks into the d5 pawn's capture.", {}),
    ("hanging_own", "4k3/8/8/3p4/8/3Q4/8/4K3 w - - 0 1", "d3d2", "taken",
     "Qd2 is safe: the d5 pawn attacks only c4 and e4, so nothing on d2 can be captured.", {}),
    ("hanging_own", "6k1/8/8/3p4/4Q3/8/8/4K3 w - - 0 1", "e4d4", "taken",
     "The queen was attacked by the d5 pawn; Qd4 moves it to a safe square.", {}),
    ("hanging_own", "6k1/8/8/3p4/4Q3/8/8/4K3 w - - 0 1", "e1f1", "missed",
     "The queen is attacked by the d5 pawn and this move ignores it.", {}),
    ("hanging_own", "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1", "e2e4", "not_applicable",
     "No piece other than pawns and kings: nothing can hang.", {}),
]


def _check_adversarial_label(det, label, board, move, fen, uci):
    """My hand reasoning is checked by the independent search; a mismatch means my label is wrong."""
    where = (det, fen, uci, label)
    if det == "missed_free":
        opp = best_capture_net(board) >= MIN_GAIN
        wins = capture_net(board, move) >= MIN_GAIN
        if label == "not_applicable":
            assert not opp, where
        elif label == "taken":
            assert opp and wins, where
        elif label == "missed":
            assert opp and not wins, where
        elif label == "uncertain":
            assert opp and not wins and board.gives_check(move), where
    else:
        hangs = hang_gain_after(board, move) >= MIN_GAIN
        flags = [hang_gain_after(board, m) >= MIN_GAIN for m in board.legal_moves]
        if label == "missed":
            assert hangs and not all(flags), where
        elif label == "taken":
            assert not hangs and any(flags), where
        elif label == "not_applicable":
            assert not (any(flags) and not all(flags)), where


def build_adversarial(engine):
    out = []
    for i, (det, fen, uci, label, reason, facts) in enumerate(ADV, 1):
        board = chess.Board(fen)
        assert board.is_valid(), fen
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves, (fen, uci)
        for u in facts.get("illegal", []):  # structural facts, checked by the library only
            assert chess.Move.from_uci(u) not in board.legal_moves, (fen, u)
        if "legal_after" in facts or "illegal_after" in facts:
            first, reply = (facts.get("legal_after") or facts.get("illegal_after"))
            after = board.copy()
            after.push(chess.Move.from_uci(first))
            legal = chess.Move.from_uci(reply) in after.legal_moves
            assert legal == ("legal_after" in facts), (fen, first, reply)
        _check_adversarial_label(det, label, board, move, fen, uci)
        best_cp, after_cp, loss = engine_loss(engine, board, move)
        if label == "missed":  # an outcome WITH evidence: the engine must confirm the loss
            assert loss >= UNCERTAIN_LOSS_CP, ("engine does not confirm", fen, uci, loss)
        if label == "taken" and det == "hanging_own":
            assert loss < MISS_LOSS_CP, ("engine says this safe move loses", fen, uci, loss)
        out.append({"detector": det, "label": label, "material_label": label, "fen": fen, "move_uci": uci,
                    "engine_best_cp": best_cp, "engine_after_cp": after_cp, "loss_cp": loss,
                    "move_san": board.san(move),
                    "category": "adversarial", "constructed": True, "puzzle_id": f"adv{i:02d}", "rating": None,
                    "band": None, "mate_theme": False, "themes": [], "source_url": None, "reason": reason})
    return out


QUESTIONS = {
    "missed_free": [
        (
            "A. Before this move, could the side to move win material by capturing a knight, bishop, rook or "
            "queen, gaining at least two pawns' worth after the opponent takes back as well as it can? "
            "(A rook for a bishop counts. A trade of equal pieces does not.)"
        ),
        (
            "B. Does the move shown make such a capture, one that itself wins at least two pawns' worth after "
            "the opponent's best recapture? (Taking a piece but then losing a bigger one does not count.)"
        ),
        (
            "C. Is there something that matters more than the material here, such as checkmate or a forced win, "
            "so that skipping the capture would be fine?"
        ),
    ],
    "hanging_own": [
        (
            "A. After this move, can the opponent win at least two pawns' worth of material by capturing one of "
            "the mover's knights, bishops, rooks or queens, counting what the mover can take back?"
        ),
        (
            "B. (Answer if A is yes.) Before the move, could the mover have played some other legal move that "
            "avoids this?"
        ),
        (
            "C. (Answer if A is no.) Before the move, was there any legal move by the mover that would have left a "
            "piece (not a pawn) to be won?"
        ),
    ],
}


def sheet(rows, title):
    intro = (
        "Answer each question from the board. **Do not run the detectors.** If you cannot tell, "
        "write `can't tell`; that is allowed. Use the link to open the position and look at the move."
    )
    lines = [f"# {title}", "", intro, ""]
    for r in rows:
        board = chess.Board(r["fen"])
        who = "White" if board.turn else "Black"
        link = "https://lichess.org/analysis/" + board.fen().replace(" ", "_")
        qs = QUESTIONS[r["detector"]]
        q = "\n".join(f"  - {x}" for x in qs)
        lines += [f"## {r['id']}", f"- {who} to move; move played: **{r['move_san']}**", f"- Board: {link}",
                  "- Questions (yes / no / can't tell):", q, "- Your answers (A, B, C): ______", ""]
    return "\n".join(lines)


def main():
    if (OUT / "FROZEN.md").exists():  # a frozen set is never rebuilt in place; any change is a new version
        sys.exit("real_play_v1 is frozen (see FROZEN.md). Build a new version instead of overwriting it.")
    rng = random.Random(SEED)
    with Engine() as engine:
        real, pool_info, shortfall = build_real(rng, engine)
        na, na_short = build_not_applicable(rng)
        adv = build_adversarial(engine)
        engine_name = engine.name
    shortfall.update(na_short)
    items = real + na + adv
    items.sort(key=lambda r: (r["detector"], r["category"], r["puzzle_id"]))
    random.Random(SEED + 2).shuffle(items)  # ids must carry no information about the category or label
    for i, r in enumerate(items, 1):
        r["id"] = f"rp1-{i:03d}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "positions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in items))
    counts = {}
    for r in items:
        counts.setdefault(r["detector"], {}).setdefault(f"{r['category']}:{r['label']}", 0)
        counts[r["detector"]][f"{r['category']}:{r['label']}"] += 1
    prov = {"set": "real_play_v1", "rule": "LABEL_RULE.md v0.2", "seed": SEED, "engine": engine_name,
            "oracle_depth": ORACLE.depth, "miss_loss_cp": MISS_LOSS_CP, "puzzle_file_sha256": sha256(PUZZLES),
            "counts": counts, "pool": pool_info, "shortfall": shortfall, "items": len(items),
            "detectors_run": False, "frozen": False}
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    # hand-check sheets: labels hidden; the owner gets 30 items, the second reviewer a different 30 plus all adversarial
    rng2 = random.Random(SEED + 1)
    real_items = [r for r in items if r["category"] != "adversarial"]
    rng2.shuffle(real_items)
    owner, second = real_items[:30], real_items[30:60] + [r for r in items if r["category"] == "adversarial"]
    rng2.shuffle(owner), rng2.shuffle(second)
    (OUT / "handcheck_owner.md").write_text(sheet(owner, "Hand-check sheet: owner (30 items, labels hidden)"))
    (OUT / "handcheck_second.md").write_text(sheet(second, "Hand-check sheet: second reviewer (labels hidden)"))
    print(json.dumps(prov["counts"], indent=1)); print("shortfall:", shortfall, "| items:", len(items))


if __name__ == "__main__":
    main()
