"""The why behind a slip (ADR 0021): one plain sentence per line, built only from a detector's record and the board, with the marks to draw."""

from app.learner import slipwhy

HANG = "4k3/8/8/8/6b1/8/8/3QK3 w - - 0 1"  # the queen on d1 is attacked by the bishop on g4
HANG_EV = {"lost_piece": "other", "lost_piece_square_after": "d1", "player_move": {"uci": "e1f1"}, "refutation_line": {"uci": ["g4d1"]}}


def drill(fen, played, accepted):
    return {"fen": fen, "played": played, "accepted": accepted}


def test_a_hanging_piece_names_the_piece_the_attacker_and_the_square_and_draws_their_capture():
    why = slipwhy.build("hanging_own", drill(HANG, "e1f1", ["d1d2"]), HANG_EV, alternatives=["d1d2"])
    assert why["mine"]["text"] == "Your queen on d1 can be taken by their bishop."
    assert why["mine"]["step"] == 1 and why["mine"]["squares"] == ["d1"]
    assert why["mine"]["arrows"] == [{"from": "g4", "to": "d1", "tone": "their"}]


def test_the_better_move_is_described_by_what_it_does_on_the_board():
    away = slipwhy.build("hanging_own", drill(HANG, "e1f1", ["d1d2"]), HANG_EV, alternatives=["d1d2"])["better"]
    assert away["text"] == "This moves your queen out of danger." and away["step"] == 1
    assert away["arrows"] == [{"from": "g4", "to": "d1", "tone": "their"}]  # the threat it avoids stays on the board
    takes = slipwhy.build("hanging_own", drill(HANG, "e1f1", ["d1g4"]), HANG_EV, alternatives=["d1g4"])["better"]
    assert takes["text"] == "This takes the bishop that was about to take your queen." and takes["arrows"] == []
    defended = slipwhy.build("hanging_own", drill("4k3/8/8/8/6b1/8/8/R2Q1K2 w - - 0 1", "f1g1", ["f1e1"]),
                             {**HANG_EV, "player_move": {"uci": "f1g1"}}, alternatives=["f1e1"])["better"]
    assert defended["text"] == "This keeps your queen on d1 defended."


def test_a_better_move_that_does_none_of_those_gets_no_sentence_rather_than_a_guess():
    why = slipwhy.build("hanging_own", drill(HANG, "e1f1", ["e1f2"]), HANG_EV, alternatives=[])
    assert why["better"] is None and why["mine"]["text"]


def test_an_ignored_capture_threat_names_the_attacker_and_the_target():
    fen = "4k3/3n4/8/4B3/8/8/8/4K3 w - - 0 1"  # the knight on d7 attacks the bishop on e5
    ev = {"threat_move": {"uci": "d7e5"}, "threat_kind": "capture", "threat_line": {"uci": ["d7e5"]}}
    why = slipwhy.build("threat", drill(fen, "e1e2", ["e5d4"]), ev)
    assert why["mine"]["text"] == "They threaten to take your bishop on e5 with the knight."
    assert why["mine"]["arrows"] == [{"from": "d7", "to": "e5", "tone": "their"}] and why["mine"]["squares"] == ["e5"]
    assert why["better"]["text"] == "This moves your bishop out of the way."
    assert why["better"]["arrows"] == [{"from": "d7", "to": "e5", "tone": "their"}]


def test_a_mate_threat_a_fork_threat_and_any_other_threat_each_have_their_own_sentence():
    mate = slipwhy.build("threat", drill("r5k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1", "g1h1", []),
                         {"threat_move": {"uci": "a8a1"}, "threat_kind": "mate", "threat_line": {"uci": ["a8a1"]}})
    assert mate["mine"]["text"] == "They threaten checkmate with the rook to a1." and mate["mine"]["squares"] == ["g1"]
    fork = slipwhy.build("threat", drill("4k3/8/8/8/1n6/8/8/R3K3 w - - 0 1", "e1e2", []),
                         {"threat_move": {"uci": "b4c2"}, "threat_kind": "fork", "threat_line": {"uci": ["b4c2"]}})
    assert fork["mine"]["text"] == "They threaten a fork: the knight to c2 would attack your rook and king."
    other = slipwhy.build("threat", drill("4k3/8/8/8/1n6/8/8/R3K3 w - - 0 1", "e1e2", []),
                          {"threat_move": {"uci": "b4c2"}, "threat_kind": "other", "threat_line": {"uci": ["b4c2"]}})
    assert other["mine"]["text"] == "They threaten to win material with the knight to c2."


def test_a_missed_free_capture_is_shown_on_the_start_position_and_the_better_move_that_takes_it_says_so():
    fen = "4k3/8/8/3r4/8/8/3Q4/4K3 w - - 0 1"
    ev = {"free_captures": [{"uci": "d2d5", "san": "Qxd5"}]}
    why = slipwhy.build("missed_free", drill(fen, "e1f1", ["d2d5"]), ev)
    assert why["mine"] == {"step": 0, "text": "You could win their rook on d5 with your queen.",
                           "arrows": [{"from": "d2", "to": "d5", "tone": "better"}], "squares": ["d5"]}
    assert why["better"]["text"] == "This wins the rook on d5." and why["better"]["step"] == 1


def test_other_has_no_why_and_a_record_that_does_not_fit_the_board_gives_none_not_an_error():
    assert slipwhy.build("other", drill(HANG, "e1f1", []), {}) is None
    assert slipwhy.build("hanging_own", drill(HANG, "e1f1", []), {"refutation_line": {"uci": ["a1a2"]}, "lost_piece": "other",
                                                                  "lost_piece_square_after": "a2"}) is None
