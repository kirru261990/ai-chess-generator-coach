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
