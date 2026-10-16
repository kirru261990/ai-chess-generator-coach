# ruff: noqa: F811
"""Practice as chat tools: a full session through the tool functions with the scripted engine, every refusal a sentence, and the
leak test over the messages shown before the first answer."""

import re
from contextlib import contextmanager

import chess
import pytest

from app.learner import practice as P
from app.mcp import practice_tools as T
from tests.test_assessment import Store
from tests.test_practice import (  # noqa: F401
    M1_PRACTICE,
    M1_PRACTICE_FEN,
    FakeAnalyser,
    conn,
    make_store,
    store,
)

SID = re.compile(r"session (\d+)")


@contextmanager
def opener(_conn):
    yield FakeAnalyser()


def sid_of(text):
    return int(SID.search(text).group(1))


def started(conn, t="pieces_in_danger"):
    text = T.practice_start(conn, t)
    return sid_of(text), text


def fens_in(conn, pool):
    return [r[0] for r in conn.execute("SELECT fen FROM position WHERE pool = ?", (pool,))]


# --- a full session --------------------------------------------------------------------------------------------------------


def test_a_full_session_through_the_tools(store):
    conn = store.conn
    sid, text = started(conn)
    assert "position 1 of 5" in text and "assisted practice" in text and "Step 1" in text
    assert "Which of YOUR pieces can the other side win?" in text
    for i in range(5):
        text = T.practice_answer(conn, sid, "a1")
        assert "Step 2" in text and "the piece on a1" in text
        text = T.practice_move(conn, sid, "Ra2", opener)
        assert "SOUND" in text and "You chose the piece on a1: right." in text
        if i == 0:
            text = T.practice_retry(conn, sid)  # a retry is a new try of the same position
            assert "position 1 of 5" in text and "(try 2)" in text
            text = T.practice_answer(conn, sid, "a1")
            text = T.practice_move(conn, sid, "a1a2", opener)
        text = T.practice_next(conn, sid)
    assert "finished" in text and "Positions completed: 5 of 5" in text and "delayed test" in text.lower()
    assert T.practice_summary(conn, sid) == text
    assert "Right on the first try with no hint: 5" in text  # a retry never changes the first attempt
    assert "Needed another try: 1" in text


def test_a_wrong_move_gets_the_checked_feedback_and_good_moves(store):
    conn = store.conn
    sid, _ = started(conn)
    T.practice_answer(conn, sid, "g1")
    text = T.practice_move(conn, sid, "Kf1", opener)
    assert "NOT SOUND" in text and "You chose the piece on g1: not right." in text
    assert "Squares in [brackets]" in text and "[♖]" in text  # the piece at risk is marked after the move
    assert "practice_retry" in text and "practice_next" in text


def test_no_threat_answer_in_words(store):
    conn = store.conn
    sid, _ = started(conn)
    text = T.practice_answer(conn, sid, "No immediate threat")
    assert 'Your answer: "No immediate threat"' in text


# --- refusals ----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("call", [
    lambda c, s: T.practice_move(c, s, "Ra2", opener),       # the question comes first
    lambda c, s: T.practice_retry(c, s),                      # nothing to retry yet
    lambda c, s: T.practice_next(c, s),                       # feedback not reached
    lambda c, s: T.practice_summary(c, s),                    # not finished
    lambda c, s: T.practice_answer(c, s, "z9"),               # not a square
    lambda c, s: T.practice_answer(c, s, "e8"),               # not a piece we may name
    lambda c, s: T.practice_answer(c, s, "c3"),               # the other side's piece
    lambda c, s: T.practice_show(c, s + 999),                 # no such session
    lambda c, s: T.practice_start(c, "forks"),                # no such type
])
def test_a_refused_step_is_one_sentence(store, call):
    conn = store.conn
    sid, _ = started(conn)
    text = call(conn, sid)
    assert text.startswith("I could not do that: ")
    assert "Traceback" not in text and "sqlite" not in text.lower() and "/" not in text.replace("n/a", "")


def test_repeating_a_step_steers_back(store):
    conn = store.conn
    sid, _ = started(conn)
    T.practice_answer(conn, sid, "a1")
    again = T.practice_answer(conn, sid, "a1")
    assert again.startswith("I could not do that") and "move step" in again and "practice_show" in again
    T.practice_move(conn, sid, "Ra2", opener)
    assert "feedback step" in T.practice_hint(conn, sid)
    assert "feedback step" in T.practice_move(conn, sid, "Ra3", opener)


def test_illegal_and_unreadable_moves_do_not_record_an_attempt(store):
    conn = store.conn
    sid, _ = started(conn)
    T.practice_answer(conn, sid, "a1")
    for bad in ("Ra9", "hello", "", "Qd4", "a1a9"):
        assert T.practice_move(conn, sid, bad, opener).startswith("I could not do that")
    assert conn.execute("SELECT COUNT(*) FROM practice_attempt WHERE move IS NOT NULL").fetchone()[0] == 0
    assert "Step 2" in T.practice_show(conn, sid)


# --- hints -------------------------------------------------------------------------------------------------------------------


def test_hints_come_one_rung_at_a_time_and_stop_at_three(store):
    conn = store.conn
    sid, text = started(conn)
    assert "[" not in text.split("```")[1]  # no marks before a hint
    t1 = T.practice_hint(conn, sid)
    assert "Hint 1:" in t1 and "Hint 2:" not in t1
    t2 = T.practice_hint(conn, sid)
    assert "Hint 2:" in t2 and "[♖]" in t2  # the piece at risk is marked
    t3 = T.practice_hint(conn, sid)
    assert "Hint 3:" in t3 and "Bxa1" in t3 and "No hints left" in t3
    assert T.practice_hint(conn, sid).startswith("I could not do that: you have used all three hints")


# --- move parsing -----------------------------------------------------------------------------------------------------------


def test_parse_move_forms():
    b = chess.Board("r3k2r/pppq1ppp/2n5/8/8/2N2N2/PPPP1PPP/R3K2R w KQkq - 0 1")
    assert T.parse_move(b, "Nd5").uci() == "c3d5"
    assert T.parse_move(b, "O-O").uci() == "e1g1" and T.parse_move(b, "0-0-0").uci() == "e1c1"
    assert T.parse_move(b, "e1g1").uci() == "e1g1"
    assert T.parse_move(b, "a2a4").uci() == "a2a4" and T.parse_move(b, "a4").uci() == "a2a4"
    assert T.parse_move(b, "Nce4").uci() == "c3e4"
    assert T.parse_move(b, "ke2").uci() == "e1e2"  # lowercase piece letter


def test_parse_move_capitalises_the_piece_letter_and_prefers_a_pawn():
    b2 = chess.Board("4k3/8/8/8/8/2p5/1P2B3/4K3 w - - 0 1")
    assert T.parse_move(b2, "bxc3").uci() == "b2c3"  # a pawn capture as written
    assert T.parse_move(b2, "bd3").uci() == "e2d3"   # the bishop


def test_parse_move_refusals_say_why():
    b = chess.Board("4k3/8/8/8/8/8/R6R/4K3 w - - 0 1")
    with pytest.raises(T.Refused, match="add the square it starts from"):
        T.parse_move(b, "Rd2")
    with pytest.raises(T.Refused, match="not a legal move"):
        T.parse_move(b, "Rb3")
    with pytest.raises(T.Refused, match="not a legal move"):
        T.parse_move(b, "a2b3")
    with pytest.raises(T.Refused, match="could not read"):
        T.parse_move(b, "xyz")
    promo = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    with pytest.raises(T.Refused, match="promotes"):
        T.parse_move(promo, "a7a8")
    assert T.parse_move(promo, "a7a8q").uci() == "a7a8q" and T.parse_move(promo, "a8=Q").uci() == "a7a8q"


# --- no leaks ----------------------------------------------------------------------------------------------------------------

LEAKY = ("Bxa1", "best", "engine", "NOT SOUND", "SOUND", "pawns better", "can be won", "refutation", "allowed", "swing",
         "points of material")


def test_nothing_is_shown_before_the_first_answer_except_the_board(store):
    conn = store.conn
    sid, first = started(conn)
    fens = [r[0] for r in conn.execute(
        "SELECT p.fen FROM practice_session_position sp JOIN position p ON p.id = sp.position_id WHERE session_id = ?"
        " ORDER BY ord", (sid,))]
    for text in (first, T.practice_show(conn, sid), T.practice_show(conn, sid), T.practice_status(conn)):
        for word in LEAKY:
            assert word not in text, (word, text)
    for text in (first, T.practice_show(conn, sid)):
        assert [f for f in fens if f + "\n" in text] == [fens[0]]  # no other board, earlier or later
        assert not any(f + "\n" in text for f in fens_in(conn, "HELDOUT"))  # no held-out board
        assert "[" not in text.split("```")[1]  # no marked square
        assert text.count("```") == 2
    # after the question is answered the answer is still not shown, and a refused move shows nothing either
    after = T.practice_answer(conn, sid, "a1")
    refused = T.practice_move(conn, sid, "Qd4", opener)
    for text in (after, refused, T.practice_show(conn, sid)):
        for word in ("Bxa1", "NOT SOUND", "right.", "not right", "[♖]"):
            assert word not in text, (word, text)


def test_status_progress_and_locked_types(conn):
    s = Store(conn)
    s.fill(m1=20, m2=20, clean=14)
    for _ in range(6):
        s.position("M1", pool="PRACTICE", fen=M1_PRACTICE_FEN.format(n=s.n + 2), override=M1_PRACTICE)
    text = T.practice_status(conn)
    assert "locked" in text and "Pieces left in danger" in text and "Free pieces to take" in text
    assert T.practice_start(conn, "pieces_in_danger").startswith("I could not do that")
    assert "Starting test: not done yet" in T.progress(conn)


def test_status_and_progress_after_practice(store):
    conn = store.conn
    assert "ready" in T.practice_status(conn)
    sid, _ = started(conn)
    assert f"open session {sid}" in T.practice_status(conn)
    again = T.practice_start(conn, "pieces_in_danger")  # starting again resumes the open session
    assert sid_of(again) == sid
    out = T.progress(conn)
    assert "Starting test, played a sound move" in out and "Assisted practice" in out and "Tests (no help)" in out


def test_an_unexpected_error_is_a_sentence_without_details(store, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("/Users/x/secret.sqlite3 DROP TABLE")
    monkeypatch.setattr(P, "get_session", boom)
    text = T.practice_show(store.conn, 1)
    assert text.startswith("I could not do that") and "secret" not in text and "DROP" not in text


# --- read-only tools really are read-only (review on PR 77) -------------------------------------------------------------------


def _writes(conn):
    return (conn.execute("SELECT COUNT(*) FROM practice_attempt").fetchone()[0],
            conn.execute("SELECT status FROM practice_session").fetchall()[0][0],
            conn.execute("SELECT COUNT(*) FROM position WHERE exposure_status = 'PRACTICED'").fetchone()[0])


def test_practice_summary_changes_nothing_even_on_an_unopened_session(store):
    conn = store.conn
    sid = P.start_session(conn, "M1")["session_id"]  # started through the web API: no attempt exists yet
    before = _writes(conn)
    assert T.practice_summary(conn, sid).startswith("I could not do that: the summary is shown when")
    assert _writes(conn) == before
    assert T.practice_summary(conn, 9999).startswith("I could not do that: there is no practice session")


def test_the_first_view_of_a_new_session_saves_its_first_attempt_so_show_is_not_read_only(store):
    conn = store.conn
    sid = P.start_session(conn, "M1")["session_id"]
    before = _writes(conn)
    T.practice_show(conn, sid)
    assert _writes(conn) != before  # it writes: the annotation must say so


def test_every_tool_annotated_read_only_leaves_the_whole_store_unchanged(store):
    conn = store.conn
    sid = P.start_session(conn, "M1")["session_id"]  # an unopened session: the case a lazy read would write on

    def dump():
        return "\n".join(conn.iterdump())
    before = dump()
    T.practice_status(conn)
    T.progress(conn)
    T.practice_summary(conn, sid)
    T.practice_summary(conn, 9999)
    assert dump() == before
