import chess
import pytest

from app.core.game import GameError, Mode, make_move, new_game, resign, set_mode, to_pgn


def play(game, *ucis):
    for u in ucis:
        make_move(game, u, game.revision)
    return game


def test_legal_move_advances_revision():
    g = new_game()
    make_move(g, "e2e4", 0)
    assert g.revision == 1 and g.board().turn == chess.BLACK


def test_illegal_move_rejected_and_state_unchanged():
    g = new_game()
    with pytest.raises(GameError) as e:
        make_move(g, "e2e5", 0)
    assert e.value.code == "illegal_move" and g.moves == []


def test_malformed_move_rejected():
    with pytest.raises(GameError) as e:
        make_move(new_game(), "zzzz", 0)
    assert e.value.code == "illegal_move"


def test_stale_revision_rejected():
    g = play(new_game(), "e2e4")
    with pytest.raises(GameError) as e:
        make_move(g, "e7e5", 0)
    assert e.value.code == "revision_conflict" and g.revision == 1


def test_promotion_requires_piece():
    g = new_game(start_fen="8/P6k/8/8/8/8/8/K7 w - - 0 1")
    with pytest.raises(GameError):
        make_move(g, "a7a8", 0)  # promotion piece missing
    make_move(g, "a7a8q", 0)
    assert g.board().piece_at(chess.A8).symbol() == "Q"


def test_checkmate_outcome_and_no_further_moves():
    g = play(new_game(), "f2f3", "e7e5", "g2g4", "d8h4")
    assert g.outcome() == {"result": "0-1", "termination": "checkmate"}
    with pytest.raises(GameError) as e:
        make_move(g, "a2a3", g.revision)
    assert e.value.code == "game_over"


def test_stalemate():
    g = new_game(start_fen="k7/8/1Q6/8/8/8/8/7K w - - 0 1")
    make_move(g, "b6c7", 0)
    assert g.outcome() == {"result": "1/2-1/2", "termination": "stalemate"}


def test_insufficient_material_draw():
    g = new_game(start_fen="k7/8/8/8/8/8/8/KB6 b - - 0 1")
    assert g.outcome()["termination"] == "insufficient_material"


def test_resign():
    g = new_game()
    resign(g, chess.WHITE)
    assert g.outcome() == {"result": "0-1", "termination": "resignation"}
    with pytest.raises(GameError):
        make_move(g, "e2e4", g.revision)


def test_switching_to_practice_marks_assisted_permanently():
    g = new_game(mode=Mode.PLAY)
    assert g.assisted is False
    set_mode(g, Mode.PRACTICE)
    set_mode(g, Mode.PLAY)
    assert g.assisted is True


def test_practice_start_is_assisted():
    assert new_game(mode=Mode.PRACTICE).assisted is True


def test_invalid_fen():
    with pytest.raises(GameError) as e:
        new_game(start_fen="not a fen")
    assert e.value.code == "invalid_fen"


def test_pgn_export_roundtrip():
    g = play(new_game(), "e2e4", "e7e5", "g1f3")
    pgn = to_pgn(g)
    assert "1. e4 e5 2. Nf3" in pgn and '[Result "*"]' in pgn and '[Assisted "false"]' in pgn


# ---- takebacks (Practice mode) ----

def practice(color=chess.WHITE, level=3):
    from app.core.game import new_game as ng

    return ng(color, Mode.PRACTICE, engine_level=level)


def test_takeback_removes_engine_reply_and_user_move():
    from app.core.game import take_back

    g = play(practice(), "e2e4", "e7e5")  # user move + engine reply
    take_back(g)
    assert g.moves == [] and g.board().turn == chess.WHITE


def test_takeback_when_engine_has_not_replied_removes_only_the_users_move():
    from app.core.game import take_back

    g = play(practice(), "e2e4")  # engine's turn
    take_back(g)
    assert g.moves == []


def test_at_most_two_takebacks_in_a_row_and_a_move_resets_the_count():
    from app.core.game import take_back

    g = play(practice(), "e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6")
    assert g.takebacks_left == 2
    take_back(g)
    take_back(g)
    assert g.moves == ["e2e4", "e7e5"] and g.takebacks_left == 0
    with pytest.raises(GameError) as e:
        take_back(g)
    assert e.value.code == "takeback_limit"
    play(g, "d2d4")  # a new move starts a fresh allowance
    assert g.takebacks_left == 2


def test_takeback_only_in_practice_and_never_after_resigning():
    from app.core.game import take_back

    g = play(new_game(engine_level=3), "e2e4", "e7e5")
    with pytest.raises(GameError) as e:
        take_back(g)
    assert e.value.code == "takeback_not_allowed" and g.takebacks_left == 0
    p = play(practice(), "e2e4", "e7e5")
    resign(p, chess.WHITE)
    with pytest.raises(GameError) as e:
        take_back(p)
    assert e.value.code == "game_over"


def test_nothing_to_take_back_when_the_engine_only_opened():
    from app.core.game import take_back

    g = play(practice(chess.BLACK), "e2e4")  # engine (white) opened; black user to move
    assert g.takebacks_left == 0
    with pytest.raises(GameError) as e:
        take_back(g)
    assert e.value.code == "nothing_to_take_back" and g.moves == ["e2e4"]


def test_black_user_takeback_returns_to_the_users_turn():
    from app.core.game import take_back

    g = play(practice(chess.BLACK), "e2e4", "e7e5", "g1f3")
    take_back(g)  # drops e5 and Nf3
    assert g.moves == ["e2e4"] and g.board().turn == chess.BLACK


def test_takeback_after_being_mated_lets_the_user_rectify():
    from app.core.game import take_back

    g = play(practice(chess.BLACK), "f2f3", "e7e5", "g2g4", "d8h4")  # black user mates; engine to move
    assert g.outcome()["termination"] == "checkmate"
    take_back(g)  # undoes the mating move only
    assert g.outcome() is None and g.moves == ["f2f3", "e7e5", "g2g4"]


def test_revision_only_goes_up_so_stale_clients_cannot_match_after_an_undo():
    from app.core.game import take_back

    g = play(practice(), "e2e4", "e7e5")
    seen = g.revision
    take_back(g)
    assert g.revision > seen
    with pytest.raises(GameError) as e:
        make_move(g, "d2d4", seen)  # the revision the client held before the undo
    assert e.value.code == "revision_conflict"


def test_takeback_keeps_the_game_assisted():
    from app.core.game import take_back

    g = play(practice(), "e2e4", "e7e5")
    take_back(g)
    set_mode(g, Mode.PLAY)
    assert g.assisted is True


# ---- regressions from the full-repository audit ----

def test_the_null_move_is_rejected_and_does_not_skip_a_turn():
    g = new_game()
    for bad in ("0000", "e2e2"):
        with pytest.raises(GameError) as e:
            make_move(g, bad, 0)
        assert e.value.code == "illegal_move"
    assert g.moves == [] and g.board().turn == chess.WHITE and g.revision == 0


def test_concurrent_moves_at_the_same_revision_cannot_both_apply(monkeypatch):
    import threading

    barrier = threading.Barrier(2)
    real_parse = chess.Board.parse_uci

    def parse_then_wait(self, uci):  # both threads reach this point before either appends
        move = real_parse(self, uci)
        try:
            barrier.wait(timeout=0.3)
        except threading.BrokenBarrierError:
            pass  # with the lock held, the second thread cannot get here: the barrier times out
        return move

    monkeypatch.setattr(chess.Board, "parse_uci", parse_then_wait)
    g = new_game()
    outcomes = []

    def submit(uci):
        try:
            make_move(g, uci, 0)
            outcomes.append("ok")
        except GameError as e:
            outcomes.append(e.code)

    threads = [threading.Thread(target=submit, args=(u,)) for u in ("e2e4", "d2d4")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(outcomes) == ["ok", "revision_conflict"]
    assert len(g.moves) == 1 and g.revision == 1
    monkeypatch.undo()
    assert g.board().turn == chess.BLACK  # the history replays cleanly


def test_a_repetition_that_the_next_move_would_create_does_not_end_the_game():
    g = play(new_game(), "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1")
    assert not g.board().is_repetition(3) and g.outcome() is None  # a claim would be prospective


def test_an_actual_threefold_repetition_ends_the_game():
    g = play(new_game(), "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8")
    assert g.outcome() == {"result": "1/2-1/2", "termination": "threefold_repetition"}
    with pytest.raises(GameError) as e:
        make_move(g, "g1f3", g.revision)
    assert e.value.code == "game_over"


def test_the_fifty_move_rule_applies_when_the_clock_actually_reaches_100():
    g = new_game(start_fen="4k3/8/8/8/8/8/8/R3K3 w - - 98 80")
    play(g, "a1a2")  # clock 99
    assert g.outcome() is None
    play(g, "e8d8")  # clock 100
    assert g.outcome() == {"result": "1/2-1/2", "termination": "fifty_moves"}
