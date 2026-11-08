"""First-slip finder (ADR 0020): the slip definition, the abstentions and the record. Engine results are scripted."""

import chess

from app.engine.evidence import EngineConfig, EvidenceAnalysis, Line
from app.learner import slipfinder as SF

CFG = EngineConfig("Stockfish 19", "nn-test.nnue", "sha", depth=18, multipv=3, hash_mb=64, threads=1)

RUY = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Na5 10. Bc2 c5 11. d4 Qc7 *"
MOVES = [m for m in RUY.replace("*", "").split() if not m.endswith(".")]
PGN = '[Event "Rated Rapid game"]\n[Site "https://lichess.org/AbCd1234"]\n[WhiteElo "900"]\n[BlackElo "1100"]\n\n' + RUY + "\n"


def fen_before(ply):
    b = chess.Board()
    for san in MOVES[:ply]:
        b.push_san(san)
    return b.fen()


class FakeAnalyser:
    """Engine lines by FEN as (uci, white-side cp) best first. `deep` is used at the evidence depth, `shallow` at the prefilter
    depth (it falls back to `deep`). A position with no script gets one line at 0 cp."""

    config = CFG

    def __init__(self, deep=None, shallow=None):
        self.deep, self.shallow, self.depths = deep or {}, shallow or {}, []

    def analyse(self, board, depth=None):
        self.depths.append(depth)
        fen = board.fen()
        script = (self.shallow.get(fen) if depth == SF.PREFILTER_DEPTH else None) or self.deep.get(fen)
        if script is None:
            move = next(iter(board.legal_moves), None)
            script = [(move.uci(), 0)] if move else []
        lines = tuple(Line(uci, (uci,), cp, None, None, depth or 18) for uci, cp in script)
        return EvidenceAnalysis(fen, CFG.at_depth(depth or 18).id, lines)


def slip_at_ply_8(loss=300):
    """White's 5th move (O-O) throws away `loss`; the best move was clearly better than the next one."""
    return {fen_before(8): [("e1e2", 0), ("d2d3", -200)], fen_before(9): [("f8c5", -loss)], fen_before(10): [("d2d3", -loss)]}


def test_a_big_loss_at_move_five_is_the_first_slip():
    r = SF.find_first_slip(PGN, FakeAnalyser(deep=slip_at_ply_8()))
    assert r["status"] == "slip"
    s = r["slip"]
    assert (s["ply"], s["fen"], s["played"], s["side"], s["loss_cp"]) == (8, fen_before(8), "e1g1", "white", 300)


def script(lines):
    """Best-first lines for White's 5th move, then the position after the move actually played (O-O) at -300."""
    return {fen_before(8): lines, fen_before(9): [("a7a6", -300)]}


def test_moves_within_fifty_centipawns_of_the_best_are_the_accepted_answers():
    r = SF.find_first_slip(PGN, FakeAnalyser(deep=script([("d1e2", 0), ("d2d3", -30), ("b1c3", -200)])))
    assert [(a["uci"], a["san"]) for a in r["slip"]["accepted"]] == [("d1e2", "Qe2"), ("d2d3", "d3")]


def test_a_line_between_fifty_and_a_hundred_worse_makes_the_position_unclear_and_it_is_skipped():
    r = SF.find_first_slip(PGN, FakeAnalyser(deep=script([("d1e2", 0), ("d2d3", -70), ("b1c3", -300)])))
    assert r == {"status": "unclear", "ply": 8}


def test_nothing_before_move_five_counts():
    scripts = {fen_before(6): [("e1e2", 0), ("d2d3", -200)], fen_before(7): [("a7a6", -900)]}  # White's 4th move, a big loss
    assert SF.find_first_slip(PGN, FakeAnalyser(deep=scripts)) == {"status": "no_slip"}


def test_a_position_that_was_already_decided_is_not_a_slip():
    scripts = {fen_before(8): [("e1e2", 700), ("d2d3", 400)], fen_before(9): [("a7a6", 100)]}  # +700 down to +100
    assert SF.find_first_slip(PGN, FakeAnalyser(deep=scripts)) == {"status": "no_slip"}


def test_a_shallow_alarm_that_the_evidence_engine_does_not_confirm_is_not_a_slip():
    eng = FakeAnalyser(deep={fen_before(9): [("a7a6", -50)]}, shallow={fen_before(9): [("a7a6", -300)]})
    assert SF.find_first_slip(PGN, eng) == {"status": "no_slip"}
    assert SF.PREFILTER_DEPTH in eng.depths and None in eng.depths  # both depths were asked


def test_a_loss_under_the_slip_size_is_not_a_slip():
    assert SF.find_first_slip(PGN, FakeAnalyser(deep=slip_at_ply_8(loss=149))) == {"status": "no_slip"}


def test_only_the_asked_players_moves_count_and_black_is_scored_from_black():
    eng = FakeAnalyser(deep=slip_at_ply_8())
    assert SF.find_first_slip(PGN, eng, color=chess.BLACK) == {"status": "no_slip"}
    black = {fen_before(9): [("f8c5", 0), ("b7b5", 250)], fen_before(10): [("d2d3", 300)]}  # Black's Be7 gives White +300
    r = SF.find_first_slip(PGN, FakeAnalyser(deep=black), color=chess.BLACK)
    assert (r["slip"]["side"], r["slip"]["ply"], r["slip"]["loss_cp"], r["slip"]["played"]) == ("black", 9, 300, "f8e7")


def test_the_record_carries_versions_and_the_played_move_is_never_an_accepted_answer():
    s = SF.find_first_slip(PGN, FakeAnalyser(deep=slip_at_ply_8()))["slip"]
    assert s["versions"] == {"slip_finder": SF.VERSION, "engine_config": CFG.id}
    assert s["played"] not in [a["uci"] for a in s["accepted"]]


def test_an_unreadable_pgn_raises():
    import pytest

    with pytest.raises(ValueError):
        SF.find_first_slip("1. e4 e5 2. Ke7 *", FakeAnalyser())


def test_scan_pgn_makes_a_drill_with_the_game_id_the_rating_and_the_source():
    from app.learner import slipbank

    d = slipbank.scan_pgn(PGN, FakeAnalyser(deep=slip_at_ply_8()), source="lichess")
    assert (d["type"], d["source"], d["game_id"], d["avg_rating"]) == ("S1", "lichess", "AbCd1234", 1000)
    own = slipbank.scan_pgn(PGN, FakeAnalyser(deep=slip_at_ply_8()), source="own", color=chess.WHITE, game_id="184848259776")
    assert own["game_id"] == "184848259776"
    assert slipbank.scan_pgn(PGN, FakeAnalyser(), source="own") is None


def test_the_drill_record_carries_the_bank_version_and_kind():
    d = SF.to_drill(SF.find_first_slip(PGN, FakeAnalyser(deep=slip_at_ply_8()))["slip"], "g", 900, "own")
    assert d["versions"]["bank"] == SF.BANK_VERSION and d["type"] == "S1"


def test_public_games_keep_only_games_where_both_players_are_rated_at_or_below_the_limit(tmp_path):
    from app.learner import slipbank

    low = PGN.replace("1100", "850").replace("AbCd1234", "LowLow11")
    high = PGN.replace('"900"', '"1500"').replace("AbCd1234", "HighHigh")
    f = tmp_path / "p.pgn"
    f.write_text(low + "\n" + high)
    assert [gid for gid, _, _ in slipbank.public_games(f, max_rating=900)] == ["LowLow11"]


def test_a_drill_already_in_the_file_is_not_written_again_and_the_resume_key_includes_the_finder_version(tmp_path):
    from app.learner import slipbank

    d = SF.to_drill(slip_at_ply_8_record(), "g", 900, "own")
    out = tmp_path / "s.jsonl"
    known = set()
    assert slipbank.append_drill(out, d, known) is True
    assert slipbank.append_drill(out, d, known) is False
    assert len(out.read_text().splitlines()) == 1
    assert SF.VERSION in slipbank.marker_key("own", "g1") and "own" in slipbank.marker_key("own", "g1")


def slip_at_ply_8_record():
    return SF.find_first_slip(PGN, FakeAnalyser(deep=slip_at_ply_8()))["slip"]


def test_a_first_slip_whose_played_move_is_also_an_accepted_answer_is_unclear():
    # the before/after searches disagree: O-O is within 50 cp of the best before the move, yet the position after it is -300
    lines = [("d1e2", 0), ("e1g1", -30), ("b1c3", -200)]
    r = SF.find_first_slip(PGN, FakeAnalyser(deep={fen_before(8): lines, fen_before(9): [("f8c5", -300)]}))
    assert r == {"status": "unclear", "ply": 8}


def test_the_same_position_found_by_a_new_finder_version_is_a_different_drill():
    s1 = slip_at_ply_8_record()
    s2 = {**s1, "versions": {**s1["versions"], "slip_finder": "2"}}
    assert SF.to_drill(s1, "g", 900, "own")["id"] != SF.to_drill(s2, "g", 900, "own")["id"]
