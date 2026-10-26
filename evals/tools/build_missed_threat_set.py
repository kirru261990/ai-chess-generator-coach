"""Build the M3 eval set `missed_threat_v1` (TASKS M3c, ADR 0011). Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/build_missed_threat_set.py

Labels come from Lichess puzzle data, a separate exchange search (build_real_play_set.py, written apart from the detectors),
Stockfish at depth 14 and hand-built positions with written reasons. LABEL_RULE.md next to the set is the rule. The set is
written once; if FROZEN.md exists the builder refuses to run.
"""

import json
import random
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_real_play_set as B

ROOT = B.ROOT
OUT = ROOT / "evals" / "sets" / "missed_threat_v1"
SEED = 20261026
ORACLE = B.ORACLE  # Stockfish, depth 14
BANDS = (400, 600, 800, 1000)
QUOTA = {"missed_real": 15, "met_real": 10, "constructed_missed": 10, "constructed_quiet": 5, "hung_not_threat": 5, "quiet_blunder": 4}
MISS_LOSS_CP = 300  # the move must lose at least this much for a `missed` label
MET_LOSS_CP = 100  # a `met` move loses less than this
THREAT_CP = 200  # passing must cost at least this much for the engine to confirm a threat
NO_THREAT_CP = 60  # passing costs less than this for a "no threat" label
DECIDED_CP = 600
NEAR_EQUAL_CP = 600
MIN_PLY = 4
SAMPLE_MOD = 25  # one puzzle in 25 (by id hash) is looked at for the general pools
MIN_GAIN = B.MIN_GAIN


def ply_of(board):
    return 2 * (board.fullmove_number - 1) + (0 if board.turn == chess.WHITE else 1)


def passed(board):
    p = board.copy(stack=False)
    p.push(chess.Move.null())
    return chess.Board(p.fen())


def gives_mate(board, move):
    board.push(move)
    mate = board.is_checkmate()
    board.pop()
    return mate


def wins(board, move):
    """The side to move wins material (>= MIN_GAIN, a non-pawn piece, after best recaptures) or mates with `move`."""
    return move in board.legal_moves and (B.capture_net(board, move) >= MIN_GAIN or gives_mate(board, move))


def static_threats(pboard):
    """Moves of the side to move in `pboard` that win material or mate at once (independent of any engine)."""
    return [m for m in pboard.legal_moves if wins(pboard, m)]


def cp(a):
    return B.cp_equiv(a.score.cp, a.score.mate, a.score.mate_sign)


def usable(board):
    return (ply_of(board) >= MIN_PLY and not board.is_check() and board.legal_moves.count() >= 2 and board.is_valid())


def band_of(rating):
    return (rating // 200) * 200


class Facts:
    """Engine numbers for one position, from the mover's side."""

    def __init__(self, engine, board):
        self.board = board
        self.mover = board.turn
        self.best = engine.analyse(board, ORACLE, perspective=self.mover)
        self.best_cp = cp(self.best)
        self.engine = engine
        self._pass = None

    @property
    def pass_cp(self):
        if self._pass is None:
            self._pass = cp(self.engine.analyse(passed(self.board), ORACLE, perspective=self.mover))
        return self._pass

    @property
    def threat_cp(self):
        return self.best_cp - self.pass_cp

    def after_cp(self, move):
        b = self.board.copy()
        b.push(move)
        if b.is_checkmate():
            return 10000
        if b.is_game_over():
            return 0
        return cp(self.engine.analyse(b, ORACLE, perspective=self.mover))

    def loss(self, move):
        return self.best_cp - self.after_cp(move)


def row(label, category, board, move, p, facts, **extra):
    r = {"label": label, "category": category, "constructed": category.startswith("constructed"),
         "fen": board.fen(), "move_uci": move.uci(), "move_san": board.san(move), "ply": ply_of(board),
         "puzzle_id": p["id"], "rating": p["rating"], "band": p["band"], "themes": p["themes"],
         "mate_theme": p["mate_theme"], "source_url": f"https://lichess.org/training/{p['id']}",
         "engine_best_cp": facts.best_cp, **extra}
    return r


def load_pools():
    """General sample (1 in SAMPLE_MOD by id hash) and every defensiveMove puzzle, both rated 400 to 1199."""
    import hashlib
    sample, defensive = [], []
    for p in B.load_puzzles():
        if "defensiveMove" in p["themes"]:
            defensive.append(p)
        if int(hashlib.sha256(p["id"].encode()).hexdigest(), 16) % SAMPLE_MOD == 0:
            sample.append(p)
    return sample, defensive


# --- the four pools -------------------------------------------------------------------------------------------------

def missed_real(p, engine):
    """The solver's reply b was already winning when X (the mover of Moves[0]) passed; X ignored it. Real play."""
    q = B.prepare(p)
    if not q:
        return None
    F, a, b, after = q["before"], q["m0"], q["m1"], q["after"]
    if not usable(F):
        return None
    pb = passed(F)
    if not (wins(pb, b) and wins(after, b)):
        return None
    f = Facts(engine, F)
    if abs(f.best_cp) > DECIDED_CP:
        return None
    loss = f.loss(a)
    e = chess.Move.from_uci(f.best.pv[0])
    if loss < MISS_LOSS_CP or e == a:
        return None
    after_e = F.copy()
    after_e.push(e)
    if wins(after_e, b):  # the engine's own best move does not stop this threat: not a clean "missed" case
        return None
    return row("missed", "missed_real", F, a, q, f, threat_move=b.uci(), threat_basis="static", engine_after_cp=f.best_cp - loss,
               loss_cp=loss, engine_best_move=e.uci())


def defensive_base(p, engine):
    """(prepared puzzle, Facts, static threat list) for a position where the solver faces a real threat, or None."""
    q = B.prepare(p)
    if not q:
        return None
    P = q["after"]
    if not usable(P):
        return None
    threats = static_threats(passed(P))
    f = Facts(engine, P)
    if abs(f.best_cp) > DECIDED_CP or f.threat_cp < THREAT_CP:
        return None
    return q, f, threats


def met_real(p, engine):
    base = defensive_base(p, engine)
    if not base:
        return None
    q, f, threats = base
    loss = f.loss(q["m1"])
    if loss >= MET_LOSS_CP:
        return None
    return row("met", "met_real", q["after"], q["m1"], q, f, previous_fen=q["before"].fen(),
               threat_basis="static" if threats else "engine_only", threat_cp=f.threat_cp, loss_cp=loss,
               threat_moves=[m.uci() for m in threats])


def constructed_missed(p, engine, rng):
    base = defensive_base(p, engine)
    if not base:
        return None
    q, f, threats = base
    if not threats:  # static basis only: the same threat must be checkable without the engine
        return None
    P = q["after"]
    moves = [m for m in P.legal_moves if m != q["m1"]]
    rng.shuffle(moves)
    for m in moves[:8]:
        after = P.copy()
        after.push(m)
        if not any(wins(after, t) for t in threats):  # the threat still works after the move
            continue
        loss = f.loss(m)
        if loss >= MISS_LOSS_CP:
            return row("missed", "constructed_missed", P, m, q, f, previous_fen=q["before"].fen(), threat_basis="static",
                       threat_cp=f.threat_cp, loss_cp=loss, threat_moves=[t.uci() for t in threats])
    return None


def constructed_quiet(p, engine):
    """Nothing is threatened before the move (X to move in the puzzle's first position); the move is the engine's best."""
    q = B.prepare(p)
    if not q:
        return None
    F = q["before"]
    if not usable(F) or static_threats(passed(F)) or B.best_capture_net(passed(F)) >= 1:
        return None
    f = Facts(engine, F)
    if abs(f.best_cp) > DECIDED_CP or f.threat_cp >= NO_THREAT_CP:
        return None
    e = chess.Move.from_uci(f.best.pv[0])
    return row("not_applicable", "constructed_quiet", F, e, q, f, threat_cp=f.threat_cp, loss_cp=0)


def blunder_without_threat(p, engine, want_hang):
    """X had no threat to meet, and played Moves[0], which hangs a piece (want_hang) or allows some other tactic."""
    q = B.prepare(p)
    if not q:
        return None
    F, a, after = q["before"], q["m0"], q["after"]
    if not usable(F) or static_threats(passed(F)) or B.best_capture_net(passed(F)) >= 1:
        return None
    hangs = B.best_capture_net(after) >= MIN_GAIN
    if hangs != want_hang:
        return None
    f = Facts(engine, F)
    if abs(f.best_cp) > DECIDED_CP or f.threat_cp >= NO_THREAT_CP:
        return None
    loss = f.loss(a)
    if loss < MISS_LOSS_CP:
        return None
    return row("not_applicable", "hung_not_threat" if want_hang else "quiet_blunder", F, a, q, f, threat_cp=f.threat_cp,
               loss_cp=loss)


# --- hand-built positions -------------------------------------------------------------------------------------------
# (fen, move, label, reason). Every one is checked below by the independent search and the engine; a mismatch stops the build.
def line(*sans):
    """The FEN after playing these SAN moves from the start."""
    b = chess.Board()
    for san in sans:
        b.push_san(san)
    return b.fen()


RUY = ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "b5")  # White to move: ...b5 attacks the bishop
SCHOLAR = ("e4", "e5", "Qh5", "Nc6", "Bc4")  # Black to move: Qxf7 is mate
KNIGHT = ("e4", "Nc6", "Nf3", "Nf6", "e5")  # Black to move: e5 attacks the knight

ADV = [
    (line("d4", "d5", "c4", "e6", "Nc3", "Nf6"), "g1f3", "not_applicable",
     "A quiet queen's pawn opening position: no piece is attacked and nothing is threatened."),
    ("8/8/3k4/3P4/3K4/8/8/8 b - - 0 40", "d6d7", "not_applicable",
     "A king and pawn ending where only the move order matters: the opponent threatens nothing concrete."),
    (line("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "d3"), "d8h4", "not_applicable",
     "A quiet opening position: the queen move hangs the queen (an M1 mistake), but nothing was threatened before it."),
    ("6k1/1r3ppp/8/8/8/8/1P3PPP/3R2K1 b - - 0 20", "b7b2", "missed",
     "White threatens Rd8 mate; Rxb2 grabs a pawn and allows it. Many moves (h6, Rb8, Rd7...) meet it."),
    ("r3k3/pp3ppp/8/3N4/8/8/PPP2PPP/4K3 b - - 0 15", "h7h6", "missed",
     "White threatens Nc7+ forking king and rook; h6 ignores it. Moving the rook or covering c7 meets it."),
    ("r1bqkb1r/pppp1ppp/2n2n2/4p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 5 4", "h7h6", "missed",
     "The Fried Liver set-up: Nxf7 forks queen and rook. h6 ignores it; d5 meets it."),
    ("n5kr/5ppp/8/PN6/4B3/8/6PP/4K3 b - - 0 30", "g8f8", "uncertain",
     "The knight on a8 is attacked by the bishop with no flight square and nothing can interpose or defend it: no move stops the loss."),
    (line(*RUY), "a4b3", "met", "...bxa4 would win the bishop; Bb3 retreats it."),
    (line(*RUY), "e1g1", "missed", "...bxa4 wins the bishop; castling ignores it."),
    (line(*KNIGHT), "f6d5", "met", "exf6 would win the knight; Nd5 moves it to a safe square."),
    (line(*KNIGHT), "d7d6", "missed", "exf6 wins the knight for a pawn (net 2); d6 ignores it."),
    (line(*SCHOLAR), "g8f6", "missed", "Qxf7 is mate; Nf6 does not stop it (g6 or Qe7 would)."),
    (line(*SCHOLAR), "g8h6", "met", "Qxf7 is mate; Nh6 covers f7."),
]


def adversarial(engine):
    out, rejected = [], []
    for i, (fen, uci, label, reason) in enumerate(ADV, 1):
        board = chess.Board(fen)
        assert board.is_valid(), fen
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves, (fen, uci)
        f = Facts(engine, board)
        loss = f.loss(move)
        threats = static_threats(passed(board)) if not board.is_check() else []
        engine_threat = f.threat_cp >= THREAT_CP  # passing costs a lot: covers forks and other threats with no capture yet
        still = []
        if threats:
            after = board.copy()
            after.push(move)
            still = [t for t in threats if wins(after, t)]
        problems = []
        if label == "missed" and not ((still or (not threats and engine_threat)) and loss >= MISS_LOSS_CP):
            problems.append(("missed", [t.uci() for t in threats], f.threat_cp, loss))
        if label == "met" and not ((threats or engine_threat) and loss < MET_LOSS_CP):
            problems.append(("met", [t.uci() for t in threats], f.threat_cp, loss))
        if label == "not_applicable" and (threats or f.threat_cp >= NO_THREAT_CP):
            problems.append(("has a threat", [t.uci() for t in threats], f.threat_cp))
        if label == "uncertain":
            unavoidable = bool(threats) and all(
                any(wins(_after(board, m), t) for t in threats) or B.best_capture_net(_after(board, m)) >= MIN_GAIN
                for m in board.legal_moves)
            if not unavoidable:
                problems.append(("uncertain: some move may stop the threat", [t.uci() for t in threats]))
        if abs(f.best_cp) > DECIDED_CP:
            problems.append(("decided", f.best_cp))
        if board.is_check() or ply_of(board) < MIN_PLY:
            problems.append(("gate", ply_of(board)))
        if problems:
            rejected.append({"fen": fen, "move": uci, "label": label, "problems": problems, "best_cp": f.best_cp, "loss": loss})
            continue
        out.append({"label": label, "category": "adversarial", "constructed": True, "fen": fen, "move_uci": uci,
                    "move_san": board.san(move), "ply": ply_of(board), "puzzle_id": f"adv{i:02d}", "rating": None, "band": None,
                    "themes": [], "mate_theme": False, "source_url": None, "reason": reason, "engine_best_cp": f.best_cp,
                    "loss_cp": loss, "threat_cp": f.threat_cp, "threat_moves": [t.uci() for t in threats]})
    return out, rejected


def _after(board, move):
    b = board.copy()
    b.push(move)
    return b


# --- build ----------------------------------------------------------------------------------------------------------

def fill(candidates, test, quota_key, taken_ids, rng, shortfall, engine_stats):
    """Take items for each band until the quota is met; a puzzle supports at most one item in the whole set."""
    out = []
    by_band = {b: [p for p in candidates if p["band"] == b and p["id"] not in taken_ids] for b in BANDS}
    for b in BANDS:
        rng.shuffle(by_band[b])
        got = 0
        for p in by_band[b]:
            if p["id"] in taken_ids:
                continue
            engine_stats["tried"] = engine_stats.get("tried", 0) + 1
            r = test(p)
            if r:
                out.append(r)
                taken_ids.add(p["id"])
                got += 1
                if got >= QUOTA[quota_key]:
                    break
        if got < QUOTA[quota_key]:
            shortfall[f"{quota_key}:{b}"] = QUOTA[quota_key] - got
    return out


def main():
    if (OUT / "FROZEN.md").exists():
        sys.exit("missed_threat_v1 is frozen (see FROZEN.md). Build a new version instead of overwriting it.")
    rng = random.Random(SEED)
    sample, defensive = load_pools()
    for p in sample + defensive:
        p["mate_theme"] = any(t.startswith("mate") or t.endswith("Mate") for t in p["themes"])
    print("pools:", len(sample), "general,", len(defensive), "defensive", flush=True)
    taken, shortfall, stats = set(), {}, {}
    items = []
    with B.Engine() as engine:
        engine_name = engine.name
        items += fill(defensive, lambda p: met_real(p, engine), "met_real", taken, rng, shortfall, stats)
        print("met_real", len(items), flush=True)
        n = len(items)
        items += fill(defensive, lambda p: constructed_missed(p, engine, rng), "constructed_missed", taken, rng, shortfall, stats)
        print("constructed_missed", len(items) - n, flush=True)
        n = len(items)
        items += fill(sample, lambda p: missed_real(p, engine), "missed_real", taken, rng, shortfall, stats)
        print("missed_real", len(items) - n, flush=True)
        n = len(items)
        items += fill(sample, lambda p: constructed_quiet(p, engine), "constructed_quiet", taken, rng, shortfall, stats)
        items += fill(sample, lambda p: blunder_without_threat(p, engine, True), "hung_not_threat", taken, rng, shortfall, stats)
        items += fill(sample, lambda p: blunder_without_threat(p, engine, False), "quiet_blunder", taken, rng, shortfall, stats)
        print("negatives", len(items) - n, flush=True)
        adv, rejected = adversarial(engine)
    items += adv
    items.sort(key=lambda r: (r["category"], r["puzzle_id"]))
    random.Random(SEED + 2).shuffle(items)  # ids carry no information about the category or label
    for i, r in enumerate(items, 1):
        r["id"] = f"mt1-{i:03d}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "positions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in items))
    counts = {}
    for r in items:
        counts[f"{r['category']}:{r['label']}"] = counts.get(f"{r['category']}:{r['label']}", 0) + 1
    prov = {"set": "missed_threat_v1", "rule": "LABEL_RULE.md", "seed": SEED, "engine": engine_name, "oracle_depth": ORACLE.depth,
            "miss_loss_cp": MISS_LOSS_CP, "met_loss_cp": MET_LOSS_CP, "threat_cp": THREAT_CP, "no_threat_cp": NO_THREAT_CP,
            "decided_cp": DECIDED_CP, "min_ply": MIN_PLY, "puzzle_file_sha256": B.sha256(B.PUZZLES), "counts": counts,
            "pool": {"general_sample": len(sample), "defensive": len(defensive)}, "shortfall": shortfall,
            "adversarial_rejected": rejected, "items": len(items), "detectors_run": False, "frozen": False}
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    print(json.dumps(counts, indent=1))
    print("shortfall:", shortfall, "| rejected adversarial:", len(rejected), "| items:", len(items))
    for r in rejected:
        print("REJECTED", r)


if __name__ == "__main__":
    main()
