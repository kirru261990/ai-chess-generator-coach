import chess
import pytest

from app.learner.hints import CUES, MAX_LEVEL, consequences, cue_kind, ladder


def test_each_level_reveals_only_up_to_that_step():
    b = chess.Board()
    for level in range(1, MAX_LEVEL + 1):
        r = ladder(b, "e2e4", level)
        assert [s["level"] for s in r["steps"]] == list(range(1, level + 1))
    for level in (1, 2):  # the nudge and the cue name no square or move
        text = str(ladder(b, "e2e4", level))
        assert "e2" not in text and "e4" not in text


def test_the_ladder_follows_spec_d4():
    # scan -> concept cue -> piece/square -> consequence -> answer
    kinds = [s["kind"] for s in ladder(chess.Board(), "g1f3", MAX_LEVEL)["steps"]]
    assert MAX_LEVEL == 5 and kinds[2:] == ["piece", "consequence", "move"]


def test_piece_step_names_the_piece_and_square_and_last_step_the_move():
    r = ladder(chess.Board(), "g1f3", 5)
    assert r["steps"][2]["text"] == "Look at your knight on g1." and r["steps"][2]["from"] == "g1"
    assert "f3" not in r["steps"][3]["text"]  # the consequence does not give the move away
    last = r["steps"][4]
    assert last["uci"] == "g1f3" and last["to"] == "f3" and "Nf3" in last["text"]


def test_level_is_clamped():
    assert ladder(chess.Board(), "e2e4", 99)["level"] == MAX_LEVEL
    assert ladder(chess.Board(), "e2e4", 0)["level"] == 1


def test_the_first_step_needs_no_engine_move_and_later_steps_do():
    assert [s["kind"] for s in ladder(chess.Board(), None, 1)["steps"]] == ["scan"]
    with pytest.raises(ValueError):
        ladder(chess.Board(), None, 2)


def kind(fen, uci):
    return cue_kind(chess.Board(fen), chess.Move.from_uci(uci))


def test_cue_kinds():
    start = chess.STARTING_FEN
    assert kind(start, "g1f3") == "develop"
    assert kind(start, "e2e4") == "centre"
    assert kind(start, "a2a3") == "quiet"  # a quiet move, nothing tactical
    assert kind("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "e4d5") == "capture"
    assert kind("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1", "e1g1") == "castle"
    # Black's queen on h4 checks White's king: any reply is "get out of check"
    assert kind("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3", "e1f2") == "get_out_of_check"
    # a quiet move that gives check
    assert kind("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "f1b5") == "check"


def test_a_quiet_promotion_is_a_promotion_not_a_quiet_move():
    # endgame: the a-pawn queens with no capture and no check
    assert kind("8/P7/8/8/8/8/5k2/3K4 w - - 0 50", "a7a8q") == "promote"


def test_develop_needs_a_piece_that_has_not_moved():
    b = chess.Board()
    for uci in ("g1f3", "g8f6", "f3g1", "f6g8"):  # both knights went out and came back
        b.push_uci(uci)
    assert cue_kind(b, chess.Move.from_uci("g1f3")) == "quiet"
    assert cue_kind(b, chess.Move.from_uci("b1c3")) == "develop"  # the other knight never moved
    # a knight that is already out is not "a piece you have not moved"
    b = chess.Board("rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq - 2 2")
    assert cue_kind(b, chess.Move.from_uci("f3g5")) == "quiet"


def test_a_defensive_move_gets_the_danger_cue_and_says_what_it_saves():
    # White's knight on e5 is attacked by the d6 pawn and undefended; the best move retreats it
    fen = "rnbqkbnr/ppp2ppp/3p4/4N3/8/8/PPPPPPPP/RNBQKB1R w KQkq - 0 3"
    assert kind(fen, "e5f3") == "danger"
    assert consequences(chess.Board(fen), chess.Move.from_uci("e5f3")) == ["It moves your knight out of danger."]


def test_no_cue_claims_more_than_the_rules_checked():
    # "No tactic is on" and "Improve your least active piece" were claims nothing verified (v1)
    assert all("No tactic" not in text and "least active" not in text for text in CUES.values())


def test_every_kind_has_a_cue():
    assert set(CUES) == {"get_out_of_check", "castle", "promote", "capture", "check", "danger", "develop", "quiet",
                         "centre"}


def facts(fen, uci):
    return consequences(chess.Board(fen), chess.Move.from_uci(uci))


def test_consequences_are_checked_facts():
    assert facts("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "e4d5") == ["It takes their pawn."]
    # fool's mate
    assert facts("rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2", "d8h4") == ["It is checkmate."]
    assert facts("8/P7/8/8/8/8/5k2/3K4 w - - 0 50", "a7a8q") == ["Your pawn becomes a queen."]
    assert facts("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1", "e1g1") == [
        "It castles: your king goes to g1."]
    assert facts(chess.STARTING_FEN, "a2a3") == [
        "It is a quiet move: no capture, check or direct threat. The engine rates it the best move here."]


def test_consequence_names_an_attacked_loose_piece_and_a_saved_one():
    # Black's knight on c6 is undefended; d4-d5 attacks it
    fen = "r1bqkb1r/pppp1ppp/2n5/8/3P4/8/PPP2PPP/RNBQKBNR w KQkq - 0 5"
    assert "It attacks their knight on c6, which is not safely defended." in facts(fen, "d4d5")
    # White's bishop on b5 is attacked by the a6 pawn: retreating it
    fen = "rnbqkbnr/1ppp1ppp/p7/1B2p3/4P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 3"
    assert "It moves your bishop out of danger." in facts(fen, "b5a4")
    # White's knight on d4 is attacked by the b6 bishop and undefended: c2-c3 defends it
    fen = "rnbqk1nr/pppp1ppp/1b6/8/3N4/8/PPPPPPPP/RNBQKB1R w KQkq - 0 4"
    assert facts(fen, "c2c3") == ["It saves your knight on d4, which could have been taken."]


def test_consequence_says_when_a_mate_threat_is_stopped():
    # Black threatens Qxf2# (queen h4, bishop c5); Qe2 defends f2
    fen = "rnb1k1nr/pppp1ppp/8/2b1p3/4P2q/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 4"
    assert "It stops their checkmate threat." in facts(fen, "d1e2")
