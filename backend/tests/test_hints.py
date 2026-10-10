import chess

from app.learner.hints import CUES, MAX_LEVEL, cue_kind, ladder


def test_each_level_reveals_only_up_to_that_step():
    b = chess.Board()
    for level in range(1, MAX_LEVEL + 1):
        r = ladder(b, "e2e4", level)
        assert [s["level"] for s in r["steps"]] == list(range(1, level + 1))
    for level in (1, 2):  # the nudge and the cue name no square or move
        text = str(ladder(b, "e2e4", level))
        assert "e2" not in text and "e4" not in text


def test_piece_step_names_the_piece_and_square_and_last_step_the_move():
    r = ladder(chess.Board(), "g1f3", 4)
    assert r["steps"][2]["text"] == "Look at your knight on g1." and r["steps"][2]["from"] == "g1"
    last = r["steps"][3]
    assert last["uci"] == "g1f3" and last["to"] == "f3" and "Nf3" in last["text"]


def test_level_is_clamped():
    assert ladder(chess.Board(), "e2e4", 99)["level"] == MAX_LEVEL
    assert ladder(chess.Board(), "e2e4", 0)["level"] == 1


def kind(fen, uci):
    return cue_kind(chess.Board(fen), chess.Move.from_uci(uci))


def test_cue_kinds():
    start = chess.STARTING_FEN
    assert kind(start, "g1f3") == "develop"
    assert kind(start, "e2e4") == "centre"
    assert kind(start, "a2a3") == "improve"  # a quiet move, nothing tactical
    assert kind("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "e4d5") == "capture"
    assert kind("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1", "e1g1") == "castle"
    # Black's queen on h4 checks White's king: any reply is "get out of check"
    assert kind("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3", "e1f2") == "get_out_of_check"
    # a quiet move that gives check
    assert kind("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "f1b5") == "check"


def test_every_kind_has_a_cue():
    assert set(CUES) == {"get_out_of_check", "castle", "capture", "check", "danger", "develop", "improve", "centre"}
