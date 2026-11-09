"""First-slip hand-check (ADR 0020): the sample, the frozen page and the scoring. Uses a scratch bank, never data/drills."""

import json

import chess
import pytest

from app.learner import drillbank, slipcheck, slipfinder

START = chess.Board().fen()


def drill(n, source="own", game=None):
    return {"id": f"s{n:03d}", "type": "S1", "source": source, "fen": START, "side": "white", "played": "a2a3", "played_san": "a3",
            "game_id": game or f"g{n}", "avg_rating": 500 + n, "accepted": ["e2e4", "d2d4"],
            "evidence": {"loss_cp": 300, "accepted": [{"uci": "e2e4", "san": "e4", "cp": 20}, {"uci": "d2d4", "san": "d4", "cp": 10}]},
            "versions": {"slip_finder": slipfinder.VERSION, "engine_config": "ec-x", "bank": slipfinder.BANK_VERSION}}


@pytest.fixture
def bank(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drillbank.bank_dir().mkdir(parents=True)
    drills = [drill(n) for n in range(80)]
    drills.append(drill(900, source="lichess"))  # public-game drills are not part of this check
    drills.append(drill(901, game="g1"))  # a second drill from one game
    old = drill(902)
    old["versions"] = {**old["versions"], "slip_finder": "0"}
    drills.append(old)  # built by an older finder
    p = drillbank.bank_dir() / "slips_v1.jsonl"
    p.write_text("".join(json.dumps(d) + "\n" for d in drills))
    return p


def test_sample_is_30_own_drills_one_per_game_from_the_current_finder_and_ignores_bank_order(bank):
    drills = [json.loads(line) for line in bank.open()]
    s = slipcheck.sample(drills)
    assert len(s) == 30 and len({d["game_id"] for d in s}) == 30
    assert {d["source"] for d in s} == {"own"} and "s902" not in {d["id"] for d in s}
    assert slipcheck.sample(list(reversed(drills))) == s


def test_make_writes_one_card_per_drill_and_freezes_the_sample(bank):
    page = slipcheck.make().read_text()
    key = json.loads(slipcheck.key_path().read_text())
    assert [i["id"] for i in key["items"]] == [f"sc-{n:02d}" for n in range(1, 31)] and key["gate"] == 27
    assert all(f'id="sc-{n:02d}"' in page for n in range(1, 31)) and page.count("<svg") == 30 and "<!doctype" not in page
    first = slipcheck.key_path().read_text()
    bank.write_text(bank.read_text() + json.dumps(drill(500)) + "\n")
    slipcheck.make()
    assert slipcheck.key_path().read_text() == first


def test_make_refuses_when_there_are_too_few_own_drills(bank):
    bank.write_text("".join(json.dumps(drill(n)) + "\n" for n in range(12)))
    with pytest.raises(ValueError, match="30"):
        slipcheck.make()


def test_score_gate_and_unanswered(bank):
    slipcheck.make()
    ids = [i["id"] for i in json.loads(slipcheck.key_path().read_text())["items"]]

    def lines(real):
        return "\n".join(f"{i}: A {'yes' if i in real else 'no'}" for i in ids)

    ok = slipcheck.score(lines(set(ids[:27])))
    assert ok["real"] == 27 and ok["of"] == 30 and ok["passed"] and ok["unanswered"] == []
    bad = slipcheck.score(lines(set(ids[:26])))
    assert bad["real"] == 26 and not bad["passed"] and len(bad["not_real"]) == 4
    part = slipcheck.score("\n".join(f"{i}: A yes" for i in ids[:29]))
    assert part["unanswered"] == [ids[29]] and not part["passed"]  # 29 real, one unanswered: the gate needs every answer
    cant = slipcheck.score(lines(set(ids[:27])).replace(f"{ids[0]}: A yes", f"{ids[0]}: A cant"))
    assert cant["real"] == 26 and not cant["passed"]


# --- the explanation: plain English built only from engine lines, never from a language model ---

QFEN = "4k3/8/2p5/3p4/8/8/3Q4/4K3 w - - 0 1"  # White's queen can take the d5 pawn, and a pawn takes it back


class Line:
    def __init__(self, move, pv, cp=0, mate=None):
        self.move, self.pv, self.cp, self.mate, self.mate_sign, self.depth = move, tuple(pv), cp, mate, None, 18


class Result:
    def __init__(self, line):
        self.best, self.lines = line, [line]


class Scripted:
    """An analyser that answers from a table of first move -> engine line, keyed by the position's FEN."""

    def __init__(self, table):
        self.table = table

    def analyse(self, board, depth=None):
        return Result(self.table[board.fen()])


def test_explanation_says_which_material_is_lost_after_the_played_move_and_what_the_better_move_keeps():
    after_played = chess.Board(QFEN)
    after_played.push_uci("d2d5")
    after_better = chess.Board(QFEN)
    after_better.push_uci("e1f1")
    analyser = Scripted({after_played.fen(): Line("c6d5", ["c6d5"], cp=-800), after_better.fen(): Line("e8e7", ["e8e7"], cp=0)})
    why = slipcheck.explain({"fen": QFEN, "played": "d2d5", "accepted": ["e1f1"]}, analyser)
    assert "queen takes the pawn on d5" in why["played"] and "pawn takes the queen on d5" in why["played"]
    assert "8 points behind" in why["played"] and "gives up" not in why["played"]  # no loss figure without the drill's evidence
    why = slipcheck.explain({"fen": QFEN, "played": "d2d5", "accepted": ["e1f1"], "evidence": {"loss_cp": 350}}, analyser)
    assert "gives up about 3.5 pawns" in why["played"]
    assert "king to f1" in why["better"].lower() and "level" in why["better"]


def test_explanation_names_a_forced_mate_and_a_loss_with_no_material_change():
    start = chess.Board()
    played_board = start.copy()
    played_board.push_uci("f2f3")
    analyser = Scripted({played_board.fen(): Line("e7e5", ["e7e5", "g2g4", "d8h4"], cp=None, mate=-1)})
    why = slipcheck.explain({"fen": start.fen(), "played": "f2f3", "accepted": []}, analyser)
    assert "checkmate" in why["played"]
    quiet = chess.Board()
    quiet.push_uci("a2a3")
    analyser = Scripted({quiet.fen(): Line("e7e5", ["e7e5"], cp=-300)})
    why = slipcheck.explain({"fen": start.fen(), "played": "a2a3", "accepted": []}, analyser)
    assert "no material is lost" in why["played"] and "3 pawns" in why["played"]


def test_make_stores_the_explanation_in_the_frozen_key_and_shows_it_on_the_card(bank):
    class Any:
        def analyse(self, board, depth=None):
            return Result(Line(next(iter(board.legal_moves)).uci(), [next(iter(board.legal_moves)).uci()], cp=-300))

    page = slipcheck.make(analyser=Any()).read_text()
    key = json.loads(slipcheck.key_path().read_text())
    assert all(set(i["why"]) == {"played", "better"} for i in key["items"]) and page.count("Why the computer prefers it") == 30
