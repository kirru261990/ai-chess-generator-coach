"""Drill check page (ADR 0017 decision 9): the sample, the page and the scoring. Uses a tiny scratch bank, never data/drills."""

import json

import pytest

from app.learner import drillbank, drillcheck

E1 = {"fen": "rn1qk2r/p3bppp/b1p1p3/3pP2n/B2P4/NP3N2/P1PB1PPP/R2QK2R w KQkq - 1 10", "player_move": {"uci": "c2c4", "san": "c4"},
      "target_squares": ["a3"], "lost_piece_square_after": "a3", "refutation_line": {"uci": ["e7a3", "e1g1"], "san": ["Bxa3", "O-O"]}}
E2 = {"fen": "rn1qk2r/p3bppp/b1p1p3/3pP2n/B1PP4/NP3N2/P2B1PPP/R2QK2R b KQkq - 0 10", "player_move": {"uci": "e8g8", "san": "O-O"},
      "target_squares": ["a3"], "free_captures": [{"uci": "e7a3", "san": "Bxa3"}], "refutation_line": {"uci": ["e7a3", "e1g1"], "san": ["Bxa3", "O-O"]}}


def drill(n, t, game, experimental=False):
    return {"id": f"id{n:03d}", "type": t, "fen": "x", "game_id": game, "avg_rating": 900 + n, "experimental": experimental,
            "evidence": E1 if t == "M1" else E2, "alternatives": [{"uci": "a3b1", "san": "Nb1"}] if t == "M1" else [{"uci": "e7a3", "san": "Bxa3"}]}


@pytest.fixture
def bank(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drills = [drill(n, "M1" if n % 2 else "M2", f"g{n // 2}") for n in range(60)]  # games hold one M1 and one M2 drill
    drills.append(drill(99, "M1", "gx", experimental=True))
    drillbank.bank_dir().mkdir(parents=True)
    p = drillbank.bank_path()
    p.write_text("".join(json.dumps(d) + "\n" for d in drills))
    return p


def test_sample_is_ten_each_one_per_game_and_never_experimental(bank):
    drills = [json.loads(line) for line in bank.open()]
    s = drillcheck.sample(drills)
    assert [d["type"] for d in s].count("M1") == 10 and [d["type"] for d in s].count("M2") == 10
    assert len({d["game_id"] for d in s}) == 20
    assert not any(d["experimental"] for d in s)
    assert drillcheck.sample(list(reversed(drills))) == s  # the order of the bank does not matter


def test_make_freezes_the_sample_and_writes_every_card(bank):
    page = drillcheck.make(bank).read_text()
    key = json.loads(drillcheck.key_path().read_text())
    assert [i["id"] for i in key["items"]] == [f"dc-{n:02d}" for n in range(1, 21)]
    assert all(f'id="dc-{n:02d}"' in page for n in range(1, 21)) and "other players" in page
    assert "come out ahead" in page and page.count("<svg") == 30 and "<!doctype" not in page
    first = drillcheck.key_path().read_text()
    drillbank.bank_path().write_text(bank.read_text() + json.dumps(drill(500, "M1", "gnew")) + "\n")
    drillcheck.make(bank)
    assert drillcheck.key_path().read_text() == first  # the sample is frozen on the first run


def test_score_gate_and_unanswered(bank):
    drillcheck.make(bank)
    key = json.loads(drillcheck.key_path().read_text())

    def lines(real_ids):
        out = []
        for it in key["items"]:
            qs = it["questions"]
            if it["id"] in real_ids:
                out.append(f"{it['id']}: " + ", ".join(f"{q} yes" for q in qs))
            else:
                out.append(f"{it['id']}: A no")
        return "\n".join(out)

    ids = [i["id"] for i in key["items"]]
    ok = drillcheck.score(lines(set(ids[:18])))
    assert ok["real"] == 18 and ok["passed"] and ok["unanswered"] == []
    bad = drillcheck.score(lines(set(ids[:17])))
    assert bad["real"] == 17 and not bad["passed"] and len(bad["not_real"]) == 3
    partial = drillcheck.score("dc-01: A yes")  # B never answered, nothing else answered
    assert "dc-01" in partial["unanswered"] and not partial["passed"]
