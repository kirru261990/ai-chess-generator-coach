import chess
from fastapi.testclient import TestClient

from app.api.main import app
from app.learner.threats import mate_threats, threats

client = TestClient(app)


def kinds(fen):
    return [(t["kind"], t.get("square") or t.get("move")) for t in threats(chess.Board(fen))["threats"]]


def test_a_piece_the_opponent_can_win_is_reported_with_its_square():
    # White to move; the white knight on e4 is attacked by the black pawn on d5 and undefended.
    assert kinds("4k3/8/8/3p4/4N3/8/8/4K3 w - - 0 1") == [("piece_can_be_taken", "e4")]


def test_a_defended_or_safe_position_has_no_threats():
    assert kinds(chess.STARTING_FEN) == []
    assert kinds("4k3/8/5n2/8/4N3/3B4/8/4K3 w - - 0 1") == []  # an even trade: the bishop defends e4


def test_a_mate_threat_is_reported():
    # Back rank: the black rook on a8 would mate on a1 if White passed.
    fen = "r5k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1"
    assert ("mate_threat", "Ra1#") in kinds(fen)
    assert mate_threats(chess.Board("r5k1/5ppp/8/8/8/8/5PPP/1R4K1 w - - 0 1")) == []  # a rook guards the back rank


def test_in_check_is_flagged_and_has_no_mate_threat_list():
    board = chess.Board("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")
    assert threats(board)["in_check"] is True and mate_threats(board) == []


def test_threat_endpoint_is_practice_only_and_waits_for_the_users_turn():
    gid = client.post("/games", json={"mode": "play"}).json()["id"]
    assert client.get(f"/games/{gid}/threats").status_code == 403
    gid = client.post("/games", json={"mode": "practice"}).json()["id"]
    r = client.get(f"/games/{gid}/threats").json()
    assert r["threats"] == [] and r["revision"] == 0
    client.post(f"/games/{gid}/moves", json={"uci": "e2e4", "expected_revision": 0, "engine_reply": False})
    assert client.get(f"/games/{gid}/threats").json()["threats"] == []  # the opponent's turn: nothing to warn about
    assert client.get("/games/nope/threats").status_code == 404
