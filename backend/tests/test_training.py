"""Practice bank (T25) and training sessions (T44)."""

import json
from datetime import UTC, datetime, timedelta

import chess
import pytest

from app.core.game import GameError
from app.engine.stockfish import Score
from app.learner import bank
from app.learner.training import Trainer, cp_value, engine_loss

# Lichess puzzle shape: FEN is before the opponent's move (Moves[0]); the answer is Moves[1].
# White's queen on d1 can take the black queen on d5, which was left hanging by ...Qd5?? (Moves[0] here is Black's Bd6-b4?).
FREE_PIECE = {
    "PuzzleId": "AAAA1", "FEN": "rnb1kbnr/pppp1ppp/8/4p3/3qP3/2N2N2/PPPP1PPP/R1BQKB1R b KQkq - 1 4",
    "Moves": "d4e4 c3e4", "Rating": "800", "Popularity": "90", "Themes": "hangingPiece short", "RatingDeviation": "70",
}


def make_item(key, source="own", motif="hanging_own", held_out=False, game=None, fen=None, answer="e2e4"):
    """An item whose id satisfies the hash rule for `held_out` (the id is searched for, like a real bank's)."""
    n = 0
    while True:
        item_id = f"{source}:{key}-{n}"
        if bank.is_held_out(item_id if source == "own" else item_id.split(":", 1)[1]) == held_out:
            break
        n += 1
    return {"id": item_id, "source": source, "fen": fen or chess.STARTING_FEN, "answer": answer, "line": [answer],
            "motif": motif, "game": game or f"g{key}", "ply": 0, "held_out": held_out, "played": "a2a3"}


def make_bank(own=12, held=4, puzzles=8):
    items = []
    for motif in bank.OWN_MOTIFS:
        items += [make_item(f"{motif}{i}", motif=motif) for i in range(own)]
        items += [make_item(f"{motif}H{i}", motif=motif, held_out=True) for i in range(held)]
    calm = [make_item(f"calm{i}", motif="calm") for i in range(6)]
    pz = [{**make_item(f"p{i}", source="lichess", motif="missed_free"), "rating": 800} for i in range(puzzles)]
    pz += [{**make_item(f"pH{i}", source="lichess", motif="missed_free", held_out=True), "rating": 800} for i in range(3)]
    return {"bank_version": 2, "own": items, "calm": calm, "puzzles": pz}


def test_held_out_split_depends_on_the_id_alone_and_is_about_a_fifth():
    ids = [f"p{i}" for i in range(2000)]
    held = [bank.is_held_out(i) for i in ids]
    assert held == [bank.is_held_out(i) for i in ids]
    assert 0.15 < sum(held) / len(held) < 0.25


def test_puzzle_item_plays_the_opponents_move_and_keeps_the_answer():
    item = bank.puzzle_item(FREE_PIECE)
    assert item is not None
    board = chess.Board(item["fen"])
    assert board.turn == chess.WHITE and item["opponent_move"] == "d4e4" and item["answer"] == "c3e4"
    assert chess.Move.from_uci(item["answer"]) in board.legal_moves and item["motif"] == "missed_free"


def test_puzzle_item_rejects_bad_rows_mates_and_non_free_answers():
    assert bank.puzzle_item({**FREE_PIECE, "Moves": "d4e4"}) is None
    assert bank.puzzle_item({**FREE_PIECE, "Moves": "d4e4 h1h8"}) is None  # illegal answer
    assert bank.puzzle_item({**FREE_PIECE, "FEN": "garbage"}) is None
    quiet = {**FREE_PIECE, "Moves": "d4e4 d2d3"}  # a legal move that wins nothing
    assert bank.puzzle_item(quiet) is None


def test_select_puzzles_filters_theme_and_rating_and_is_deterministic():
    rows = [FREE_PIECE,
            {**FREE_PIECE, "PuzzleId": "AAAA2", "Themes": "fork"},
            {**FREE_PIECE, "PuzzleId": "AAAA3", "Rating": "2400"}]
    first = bank.select_puzzles(iter(rows))
    assert [i["id"] for i in first] == ["lichess:AAAA1"] == [i["id"] for i in bank.select_puzzles(iter(rows))]


def test_select_puzzles_caps_each_pool_separately():
    rows = [{**FREE_PIECE, "PuzzleId": f"X{i:04d}"} for i in range(400)]
    out = bank.select_puzzles(iter(rows), practice=10, held_out=3)
    assert sum(not i["held_out"] for i in out) == 10 and sum(i["held_out"] for i in out) == 3


def test_validate_catches_a_wrong_held_out_flag_and_an_illegal_answer():
    good = bank.build_bank([], bank.select_puzzles(iter([FREE_PIECE])), {})
    bank.validate(good)
    bad_flag = json.loads(json.dumps(good))
    bad_flag["puzzles"][0]["held_out"] = not bad_flag["puzzles"][0]["held_out"]
    with pytest.raises(bank.BankError):
        bank.validate(bad_flag)
    bad_answer = json.loads(json.dumps(good))
    bad_answer["puzzles"][0]["answer"] = "a1a8"
    with pytest.raises(bank.BankError):
        bank.validate(bad_answer)


def test_session_for_missed_free_has_two_own_two_practice_and_a_held_out_test_last():
    items = bank.new_session(make_bank(), "missed_free", seed=1)
    assert [i["kind"] for i in items] == ["own", "own", "practice", "practice", "held_out"]
    assert [i["source"] for i in items] == ["own", "own", "lichess", "lichess", "lichess"]
    assert items[-1]["held_out"] and not any(i["held_out"] for i in items[:-1])


def test_session_for_hanging_own_uses_own_positions_from_different_games():
    items = bank.new_session(make_bank(), "hanging_own", seed=2)
    assert [i["kind"] for i in items] == ["own"] * 4 + ["held_out"]
    assert len({i["game"] for i in items[:4]}) == 4 and all(i["motif"] == "hanging_own" for i in items)


def test_held_out_items_never_appear_as_practice_for_any_seed():
    b = make_bank()
    held_ids = {i["id"] for i in b["own"] + b["puzzles"] if i["held_out"]}
    for seed in range(60):
        for motif in bank.OWN_MOTIFS:
            for item in bank.new_session(b, motif, seed):
                assert (item["id"] in held_ids) == (item["kind"] == "held_out")


def test_session_avoids_recent_items_while_others_exist_and_is_reproducible():
    b = make_bank()
    first = bank.new_session(b, "hanging_own", seed=3)
    avoid = frozenset(i["id"] for i in first)
    second = bank.new_session(b, "hanging_own", seed=3, avoid=avoid)
    assert not {i["id"] for i in second[:4]} & {i["id"] for i in first[:4]}
    assert bank.new_session(b, "hanging_own", seed=3) == first


def test_a_bank_too_small_raises_instead_of_shortening_the_session():
    with pytest.raises(bank.BankError):
        bank.new_session(make_bank(own=3, held=0), "hanging_own", seed=1)
    with pytest.raises(bank.BankError):
        bank.new_session(make_bank(), "forks", seed=1)


def test_public_item_never_contains_the_answer():
    item = bank.new_session(make_bank(), "hanging_own", seed=1)[0]
    shown = bank.public_item(0, item)
    assert "answer" not in shown and "line" not in shown and "e2e4" not in json.dumps(shown)
    assert shown["side"] == "white" and shown["hints_allowed"] is True
    assert bank.public_item(4, {**item, "kind": "held_out"})["hints_allowed"] is False


def test_check_move_accepts_the_answer_and_engine_equivalents_only_when_measured():
    item = make_item(1)
    assert bank.check_move(item, "e2e4")["accepted_by"] == "answer"
    assert not bank.check_move(item, "d2d4")["correct"]  # no measurement: stays "not yet"
    assert bank.check_move(item, "d2d4", loss_cp=12)["accepted_by"] == "engine_equivalent"
    assert not bank.check_move(item, "d2d4", loss_cp=80)["correct"]
    assert bank.check_move(item, "e2e5")["legal"] is False and bank.check_move(item, "zzzz")["legal"] is False


# ---------------------------------------------------------------- trainer


class FakeEngine:
    """Scores the starting position +30; after d2d4 +20 (small loss); after a2a3 -50."""

    def analyse(self, board, budget, perspective=None):
        class A:
            pass

        a = A()
        after_d4 = chess.Board()
        after_d4.push_uci("d2d4")
        table = {chess.STARTING_FEN: 30, after_d4.fen(): 20}
        cp_for_white = table.get(board.fen(), -50)
        cp = cp_for_white if perspective == chess.WHITE else -cp_for_white
        a.score = Score(perspective, cp=cp)
        return a


@pytest.fixture
def trainer(tmp_path):
    (tmp_path / "bank").mkdir()
    (tmp_path / "bank" / "bank_v1.json").write_text(json.dumps(make_bank()))
    clock = {"now": datetime(2026, 10, 12, tzinfo=UTC)}
    t = Trainer(tmp_path, engine_getter=FakeEngine, now=lambda: clock["now"], budget=None)
    t.clock = clock
    return t


def test_cp_value_and_engine_loss():
    assert cp_value(Score(chess.WHITE, mate=2, mate_sign=1)) == 10_000
    assert cp_value(Score(chess.WHITE, mate=2, mate_sign=-1)) == -10_000
    b = chess.Board()
    assert engine_loss(FakeEngine(), b, chess.Move.from_uci("a2a3"), None) == 80
    assert engine_loss(FakeEngine(), b, chess.Move.from_uci("d2d4"), None) == 10


def test_start_logs_the_session_and_hides_answers(trainer):
    view = trainer.start("hanging_own")
    assert len(view["items"]) == 5 and "answer" not in json.dumps(view)
    logged = (trainer.data_dir / "training" / "sessions.jsonl").read_text().splitlines()
    assert json.loads(logged[0])["id"] == view["id"] and len(json.loads(logged[0])["items"]) == 5


def test_unknown_session_and_index_are_not_found(trainer):
    with pytest.raises(GameError) as e:
        trainer.hint("nope", 0, 1)
    assert e.value.code == "not_found"
    sid = trainer.start("hanging_own")["id"]
    with pytest.raises(GameError):
        trainer.attempt(sid, 9, "e2e4")


def test_a_clean_first_try_is_unassisted_and_finishes_the_item(trainer):
    sid = trainer.start("hanging_own")["id"]
    r = trainer.attempt(sid, 0, "e2e4")
    assert r["correct"] and r["first_try"] and not r["assisted"] and r["finished"] and r["answer"]["san"] == "e4"
    with pytest.raises(GameError) as e:
        trainer.attempt(sid, 0, "e2e4")
    assert e.value.code == "item_done"


def test_any_hint_makes_the_attempt_assisted_for_good(trainer):
    sid = trainer.start("hanging_own")["id"]
    trainer.hint(sid, 1, 1)  # even the scan prompt counts
    r = trainer.attempt(sid, 1, "e2e4")
    assert r["correct"] and r["assisted"]
    logged = [json.loads(line) for line in (trainer.data_dir / "training" / "attempts.jsonl").read_text().splitlines()]
    assert logged[-1]["assisted"] is True and logged[-1]["hints_used"] == 1


def test_a_wrong_first_try_can_retry_but_stays_a_miss_on_first_try(trainer):
    sid = trainer.start("hanging_own")["id"]
    first = trainer.attempt(sid, 0, "a2a3")  # 80 cp worse than the best: not equivalent
    assert not first["correct"] and first["first_try"] and not first["finished"] and "answer" not in first
    second = trainer.attempt(sid, 0, "e2e4")
    assert second["correct"] and not second["first_try"]


def test_an_equivalent_move_is_accepted_through_the_engine(trainer):
    sid = trainer.start("hanging_own")["id"]
    r = trainer.attempt(sid, 0, "d2d4")  # 10 cp loss
    assert r["correct"] and r["accepted_by"] == "engine_equivalent"


def test_without_an_engine_only_the_stored_answer_counts(tmp_path):
    (tmp_path / "bank").mkdir()
    (tmp_path / "bank" / "bank_v1.json").write_text(json.dumps(make_bank()))
    t = Trainer(tmp_path, engine_getter=None)
    sid = t.start("hanging_own")["id"]
    assert not t.attempt(sid, 0, "d2d4")["correct"]


def test_an_engine_failure_does_not_turn_a_good_move_into_a_wrong_one(tmp_path):
    (tmp_path / "bank").mkdir()
    (tmp_path / "bank" / "bank_v1.json").write_text(json.dumps(make_bank()))

    def broken():
        raise RuntimeError("engine down")

    t = Trainer(tmp_path, engine_getter=broken)
    sid = t.start("hanging_own")["id"]
    assert t.attempt(sid, 0, "e2e4")["correct"]  # the stored answer needs no engine


def test_the_held_out_position_has_no_hints_no_give_up_and_one_attempt(trainer):
    sid = trainer.start("hanging_own")["id"]
    for call in (lambda: trainer.hint(sid, 4, 1), lambda: trainer.give_up(sid, 4)):
        with pytest.raises(GameError) as e:
            call()
        assert e.value.code == "hint_not_allowed"
    r = trainer.attempt(sid, 4, "a2a3")
    assert not r["correct"] and r["finished"] and r["answer"]["san"] == "e4"
    with pytest.raises(GameError):
        trainer.attempt(sid, 4, "e2e4")


def test_give_up_reveals_the_answer_and_counts_as_assisted_miss(trainer):
    sid = trainer.start("hanging_own")["id"]
    r = trainer.give_up(sid, 2)
    assert r["answer"]["uci"] == "e2e4" and r["finished"]
    last = json.loads((trainer.data_dir / "training" / "attempts.jsonl").read_text().splitlines()[-1])
    assert last["gave_up"] and last["assisted"] and not last["correct"]


def test_hint_ladder_never_sends_later_steps_early(trainer):
    sid = trainer.start("hanging_own")["id"]
    r = trainer.hint(sid, 0, 2)
    assert [s["level"] for s in r["steps"]] == [1, 2] and "e2e4" not in json.dumps(r)
    assert trainer.hint(sid, 0, 1)["hints_used"] == 2  # the highest step asked for is remembered


def test_wrong_move_facts_name_a_piece_it_leaves_loose(trainer):
    fen = "4k3/8/8/8/3q4/8/8/R3K3 w - - 0 1"  # White Ra1 is safe; Kd1?? is not the point: Ra1-a4? loses the rook to Qxa4
    board = chess.Board(fen)
    facts = Trainer._facts(board, chess.Move.from_uci("a1a4"), {}, False)
    assert any("rook on a4 can be taken" in f for f in facts)


def test_retest_is_due_after_seven_days_until_solved_cleanly():
    t0 = datetime(2026, 10, 1, tzinfo=UTC)
    miss = {"at": t0.isoformat(), "item": "own:1", "kind": "own", "first_try": True, "correct": False, "assisted": False}
    held = {**miss, "item": "lichess:9", "kind": "held_out"}
    assert Trainer.retest_due([miss, held], now=t0 + timedelta(days=3)) == []
    assert Trainer.retest_due([miss, held], now=t0 + timedelta(days=8)) == ["own:1"]  # held-out items are never retested
    solved = {**miss, "at": (t0 + timedelta(days=9)).isoformat(), "first_try": True, "correct": True}
    assert Trainer.retest_due([miss, solved], now=t0 + timedelta(days=10)) == []


def test_progress_reports_counts_not_bare_rates(trainer):
    sid = trainer.start("hanging_own")["id"]
    trainer.attempt(sid, 0, "e2e4")
    trainer.attempt(sid, 1, "a2a3")
    trainer.hint(sid, 2, 1)
    trainer.attempt(sid, 2, "e2e4")
    trainer.attempt(sid, 4, "e2e4")
    p = trainer.progress()["by_motif"]["hanging_own"]
    assert p["practice_first_tries"] == 3 and p["practice_first_try_correct"] == 2
    assert p["practice_first_try_correct_unassisted"] == 1
    assert p["held_out_attempts"] == 1 and p["held_out_correct"] == 1


def test_a_missing_bank_gives_a_clear_error(tmp_path):
    with pytest.raises(GameError) as e:
        Trainer(tmp_path).start("hanging_own")
    assert e.value.code == "not_found" and "bank" in str(e.value)


def test_the_api_runs_a_session_end_to_end(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.learner import training as training_mod

    (tmp_path / "bank").mkdir()
    (tmp_path / "bank" / "bank_v1.json").write_text(json.dumps(make_bank()))
    t = Trainer(tmp_path, engine_getter=None)
    monkeypatch.setattr(training_mod, "TRAINER", t)
    monkeypatch.setattr("app.api.training.TRAINER", t)
    c = TestClient(app)
    s = c.post("/training/sessions", json={"motif": "hanging_own"}).json()
    sid = s["id"]
    assert len(s["items"]) == 5 and "answer" not in json.dumps(s)
    assert c.get(f"/training/sessions/{sid}/items/4/hint?level=1").status_code == 403
    assert c.post(f"/training/sessions/{sid}/items/0/attempt", json={"uci": "a1a1"}).status_code == 400
    r = c.post(f"/training/sessions/{sid}/items/0/attempt", json={"uci": "e2e4"}).json()
    assert r["correct"] and r["finished"]
    assert c.post(f"/training/sessions/{sid}/items/0/attempt", json={"uci": "e2e4"}).status_code == 409
    assert c.post("/training/sessions", json={"motif": "forks"}).status_code == 409
    assert c.get("/training/progress").json()["by_motif"]["hanging_own"]["practice_first_tries"] == 1


def test_the_same_move_is_judged_once_so_a_noisy_search_cannot_flip_the_verdict(tmp_path):
    (tmp_path / "bank").mkdir()
    (tmp_path / "bank" / "bank_v1.json").write_text(json.dumps(make_bank()))
    calls = []

    class Flaky:
        def analyse(self, board, budget, perspective=None):
            calls.append(board.fen())

            class A:
                pass

            a = A()
            a.score = Score(perspective, cp=-150 if len(calls) == 2 else 0)  # the first judgement says -150; a re-run would say 0
            return a

    t = Trainer(tmp_path, engine_getter=Flaky)
    sid = t.start("hanging_own")["id"]
    first = t.attempt(sid, 0, "d2d4")
    n = len(calls)
    second = t.attempt(sid, 0, "d2d4")
    assert not first["correct"] and len(calls) == n and first["correct"] == second["correct"]


# ---------------------------------------------------------------- rapid drill


def test_rapid_has_twelve_positions_in_the_planned_mix_and_held_out_only_as_tests():
    b = make_bank()
    held = {i["id"] for i in b["own"] if i["held_out"]}
    for seed in range(40):
        items = bank.new_rapid(b, seed)
        kinds = [i["kind"] for i in items]
        assert len(items) == 12 and {k: kinds.count(k) for k in set(kinds)} == {"hang": 5, "free": 2, "calm": 3, "test": 2}
        assert all((i["id"] in held) == (i["kind"] == "test") for i in items)
        assert len({i["id"] for i in items}) == 12


def test_rapid_players_are_not_told_what_kind_of_position_it_is():
    item = {**bank.new_rapid(make_bank(), 1)[0], "prev_fen": chess.STARTING_FEN, "prev_move": "e2e4"}
    shown = bank.public_rapid_item(0, item)
    text = json.dumps(shown)
    assert set(shown) == {"index", "fen", "side", "lead_in"} and "kind" not in text and "answer" not in text
    assert "lead_in" not in bank.public_rapid_item(0, {k: v for k, v in item.items() if k != "prev_fen"})


def test_rapid_needs_the_calm_pool():
    b = make_bank()
    b["calm"] = []
    with pytest.raises(bank.BankError):
        bank.new_rapid(b, 1)


def start_rapid(trainer, **kw):
    r = trainer.start_rapid(**kw)
    return r["id"], r


def test_a_rapid_try_is_one_shot_and_a_timeout_counts(trainer):
    sid, view = start_rapid(trainer)
    assert len(view["items"]) == 12 and view["limit_s"] == 10 and "answer" not in json.dumps(view)
    r = trainer.rapid_attempt(sid, 0, "e2e4", 4000)
    assert r["correct"] and not r["timed_out"] and r["kind_label"]
    with pytest.raises(GameError) as e:
        trainer.rapid_attempt(sid, 0, "e2e4", 4000)
    assert e.value.code == "item_done"
    slow = trainer.rapid_attempt(sid, 1, "e2e4", 10_000 + 1500 + 1)
    assert slow["timed_out"] and not slow["correct"] and slow["answer"]["san"]
    gone = trainer.rapid_attempt(sid, 2, None, 10_000)
    assert gone["timed_out"] and not gone["correct"]


def test_an_illegal_click_in_rapid_is_not_a_try(trainer):
    sid, _ = start_rapid(trainer)
    with pytest.raises(GameError) as e:
        trainer.rapid_attempt(sid, 0, "a1a1", 1000)
    assert e.value.code == "illegal_move"
    assert trainer.rapid_attempt(sid, 0, "e2e4", 1000)["correct"]


def test_finishing_rapid_returns_a_summary_by_kind_with_counts(trainer):
    sid, _ = start_rapid(trainer)
    last = None
    for n in range(12):
        last = trainer.rapid_attempt(sid, n, "e2e4" if n % 2 == 0 else "a2a3", 3000 + n)
    summary = last["summary"]
    assert summary["attempts"] == 12 and sum(k["attempts"] for k in summary["by_kind"].values()) == 12
    assert all(k["median_seconds"] is not None for k in summary["by_kind"].values() if k["attempts"])
    assert "summary" not in trainer.rapid_attempt(start_rapid(trainer)[0], 0, "e2e4", 1000)


def test_rapid_stays_out_of_the_practice_numbers_and_the_retest(trainer):
    sid, _ = start_rapid(trainer)
    trainer.rapid_attempt(sid, 0, "a2a3", 1000)  # a miss
    p = trainer.progress()
    assert p["by_motif"]["hanging_own"]["practice_first_tries"] == 0 and p["sessions"] == 0
    assert p["rapid"]["attempts"] == 1 and p["rapid"]["sessions"] == 1
    later = Trainer(trainer.data_dir, now=lambda: datetime(2026, 11, 1, tzinfo=UTC))
    assert later.progress()["retest_due"] == 0


def test_the_scan_prompt_fades_after_three_drills(trainer):
    flags = [trainer.start_rapid()["prompted"] for _ in range(5)]
    assert flags == [True, True, True, False, False]
    assert trainer.start_rapid()["scan_prompt"] is None


def test_a_move_that_hangs_a_piece_is_marked_careless(trainer):
    sid, _ = start_rapid(trainer)
    item = trainer.sessions[sid]["items"][0]
    item["fen"] = "4k3/8/8/8/3q4/8/8/R3K3 w - - 0 1"
    item["answer"], item["played"] = "e1d1", None
    trainer._loss_cache[(item["fen"], "a1a4")] = 900  # the engine's verdict: the rook is lost
    r = trainer.rapid_attempt(sid, 0, "a1a4", 2000)  # the rook walks into the queen
    assert r["careless"] and not r["correct"] and any("rook on a4" in f for f in r["facts"])


def test_the_rapid_api_runs_end_to_end(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.main import app

    (tmp_path / "bank").mkdir()
    (tmp_path / "bank" / "bank_v1.json").write_text(json.dumps(make_bank()))
    t = Trainer(tmp_path)
    monkeypatch.setattr("app.api.training.TRAINER", t)
    c = TestClient(app)
    v = c.post("/training/rapid", json={"limit_s": 8}).json()
    assert v["limit_s"] == 8 and len(v["items"]) == 12
    r = c.post(f"/training/rapid/{v['id']}/items/0/attempt", json={"uci": "e2e4", "elapsed_ms": 2500}).json()
    assert r["correct"]
    assert c.post(f"/training/rapid/{v['id']}/items/1/attempt", json={"uci": None, "elapsed_ms": 8000}).json()["timed_out"]


def test_validate_checks_the_lead_in_move_and_the_calm_pool():
    b = make_bank()
    board = chess.Board()
    board.push_uci("e2e4")
    b["calm"][0].update(fen=board.fen(), answer="e7e5", line=["e7e5"], prev_fen=chess.STARTING_FEN, prev_move="e2e4")
    bank.validate(b)
    b["calm"][0]["prev_move"] = "d2d4"
    with pytest.raises(bank.BankError):
        bank.validate(b)


def test_calm_items_keep_only_quiet_positions_where_the_move_cost_nothing(monkeypatch):
    class Stub:
        def __init__(self, outcome):
            self.outcome = outcome

        def detect(self, board, move, evidence):
            return type("R", (), {"outcome": self.outcome})()

    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "d2d3", "f8c5", "c2c3", "d7d6", "b1d2", "c8e6", "c4e6", "f7e6"]
    board, positions = chess.Board(), []
    for k, uci in enumerate(moves + [None]):
        positions.append({"ply": k, "fen": board.fen(), "cp": 10, "mate": None, "best": uci})
        if uci:
            board.push_uci(uci)
    analysis = {"schema": 2, "moves": moves, "positions": positions}
    game = {"source_id": "https://www.chess.com/game/live/777", "user_color": "white", "time_control": "600"}
    monkeypatch.setattr("app.learner.patterns.DETECTORS", {"a": Stub("not_applicable"), "b": Stub("not_applicable")})
    out = bank.calm_items([game], {game["source_id"]: analysis})
    assert out and all(i["ply"] >= bank.CALM_MIN_PLY and i["motif"] == "calm" and i["answer"] == moves[i["ply"]] for i in out)
    assert all(i.get("prev_move") == moves[i["ply"] - 1] for i in out)
    monkeypatch.setattr("app.learner.patterns.DETECTORS", {"a": Stub("not_applicable"), "b": Stub("missed")})
    assert bank.calm_items([game], {game["source_id"]: analysis}) == []
    for p in positions:
        p["cp"] = 10 if p["ply"] % 2 == 0 else -200  # White's move gives up 210 cp: not calm
    monkeypatch.setattr("app.learner.patterns.DETECTORS", {"a": Stub("not_applicable")})
    assert bank.calm_items([game], {game["source_id"]: analysis}) == []
