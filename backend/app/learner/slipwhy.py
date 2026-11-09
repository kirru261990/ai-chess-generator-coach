"""The why behind a slip (ADR 0021): one plain sentence for the move played and one for the better move, with the marks to draw.

Every sentence is a fixed template filled from a detector's own record (the move, the squares, the threat kind) and from the board
(python-chess): it names the piece and the square. The better move is described by what it does (moves the piece, takes the attacker,
defends the piece, blocks the line, takes the capture). When the record does not fit the board, or the better move does none of those,
there is no sentence: nothing is guessed (AGENTS rules 1, 2 and 5). No language model.

`build` returns {"mine": mark | None, "better": mark | None}; a mark is {"step", "text", "arrows": [{from, to, tone}], "squares": [...]}.
`step` is the move of the line (0 = the start position) at which the sentence is shown. Tones: their (their threat), better (the better
move or a capture you could make).
"""

from __future__ import annotations

import chess

from app.learner.slipline import POINTS

VERSION = "2"  # v2: "defends" needs a legal recapture (a pinned defender does not count); the wording and the rules of the sentences; a label made under another version is relabelled

NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
TARGET_MIN = 3  # a fork target is a piece worth this much or more, or the king (as in threat_kind.py)


def _sq(name: str) -> int:
    return chess.parse_square(name)


def _name(board: chess.Board, square: int) -> str | None:
    piece = board.piece_at(square)
    return NAMES[piece.piece_type] if piece else None


def _mark(step: int, text: str, arrows: list[dict], squares: list[str]) -> dict:
    return {"step": step, "text": text, "arrows": arrows, "squares": squares}


def _their(uci: str) -> dict:
    return {"from": uci[:2], "to": uci[2:4], "tone": "their"}


def _recapture_possible(opp_to_move: chess.Board, their_uci: str, victim_sq: int) -> bool | None:
    """After their recorded capture, can you legally recapture on the victim's square? None when the capture is no longer possible.
    Legal moves count, so a pinned defender does not."""
    move = chess.Move.from_uci(their_uci)
    if move not in opp_to_move.legal_moves:
        return None
    after_capture = opp_to_move.copy(stack=False)
    after_capture.push(move)
    return any(m.to_square == victim_sq for m in after_capture.legal_moves)


def _fix(board: chess.Board, drill: dict, victim_sq: int, attacker_sq: int, their_uci: str, victim: str, attacker: str,
         path: chess.SquareSet | None = None) -> dict | None:
    """The better move, described by what it does to a piece in danger (or a threat line). None when it does none of these."""
    if not drill["accepted"]:
        return None
    me = board.turn
    best = chess.Move.from_uci(drill["accepted"][0])
    if best not in board.legal_moves:
        return None
    after = board.copy(stack=False)
    after.push(best)
    if best.to_square == attacker_sq:
        return _mark(1, f"This takes the {attacker} that was about to take your {victim}." if path is None
                     else f"This takes the {attacker} that was making the threat.", [], [chess.square_name(victim_sq)])
    their_arrow = [_their(their_uci)]
    if best.from_square == victim_sq:
        text = f"This moves your {victim} out of danger." if path is None else f"This moves your {victim} out of the way."
        return _mark(1, text, their_arrow, [chess.square_name(victim_sq)])
    if path is not None and best.to_square in path:
        return _mark(1, "This blocks the attack.", their_arrow, [chess.square_name(victim_sq)])
    before_opp = board.copy(stack=False)
    before_opp.turn = not me  # the position before your move, with them to move: could you already recapture?
    newly_defended = (after.piece_at(victim_sq) is not None and _recapture_possible(after, their_uci, victim_sq) is True
                      and not _recapture_possible(before_opp, their_uci, victim_sq))
    if newly_defended and victim != "king":
        text = f"This defends your {victim} on {chess.square_name(victim_sq)}."
        return _mark(1, text, their_arrow, [chess.square_name(victim_sq)])
    return None


def _hanging(board: chess.Board, drill: dict, ev: dict, alternatives: list[str]) -> dict | None:
    after = board.copy(stack=False)
    after.push(chess.Move.from_uci(drill["played"]))
    their = ev["refutation_line"]["uci"][0]
    victim_sq, attacker_sq = _sq(ev["lost_piece_square_after"]), _sq(their[:2])
    victim, attacker = _name(after, victim_sq), _name(after, attacker_sq)
    if victim is None or attacker is None or _sq(their[2:4]) != victim_sq:
        return None
    where = chess.square_name(victim_sq)
    mine = _mark(1, f"Your {victim} on {where} can be taken by their {attacker}.", [_their(their)], [where])
    if ev.get("lost_piece") == "moved":
        # You moved the piece into danger, so it has no square on the better line: describe the better move only when the detector listed it as sound.
        ok = drill["accepted"] and drill["accepted"][0] in alternatives
        return {"mine": mine, "better": _mark(1, "This does not leave a piece to be taken.", [], []) if ok else None}
    return {"mine": mine, "better": _fix(board, drill, victim_sq, attacker_sq, their, victim, attacker)}


def _forks(board_after: chess.Board, square: int, victim: chess.Color) -> list[str]:
    out = []
    for sq in sorted(board_after.attacks(square)):
        p = board_after.piece_at(sq)
        if p and p.color == victim and (p.piece_type == chess.KING or POINTS[p.piece_type] >= TARGET_MIN):
            out.append(NAMES[p.piece_type])
    return out


def _uncovered(passed: chess.Board, move: chess.Move, me: chess.Color) -> tuple[int, str] | None:
    """The most valuable piece of yours that another of their pieces starts to attack once `move` is played (a discovered attack)."""
    after = passed.copy(stack=False)
    after.push(move)
    best = None
    for sq, piece in after.piece_map().items():
        if piece.color != me or (piece.piece_type != chess.KING and POINTS[piece.piece_type] < TARGET_MIN):
            continue
        new = after.attackers(not me, sq) - chess.SquareSet([move.to_square])
        if new and not passed.attackers(not me, sq):
            rank = 100 if piece.piece_type == chess.KING else POINTS[piece.piece_type]
            if best is None or rank > best[0]:
                best = (rank, sq, NAMES[piece.piece_type])
    return (best[1], best[2]) if best else None


def _threat(board: chess.Board, drill: dict, ev: dict) -> dict | None:
    me = board.turn
    passed = board.copy(stack=False)
    passed.turn = not me  # the opponent moves, as in the detector's pass test
    uci = ev["threat_move"]["uci"]
    move = chess.Move.from_uci(uci)
    attacker = _name(passed, move.from_square)
    if attacker is None:
        return None
    to = chess.square_name(move.to_square)
    kind = ev.get("threat_kind")
    victim_piece = passed.piece_at(move.to_square)
    victim_sq = move.to_square
    if kind == "mate":
        king = board.king(me)
        text, squares = f"They threaten checkmate with the {attacker} to {to}.", [chess.square_name(king)] if king is not None else []
        victim_sq = king if king is not None else move.to_square
    elif kind == "capture" and victim_piece and victim_piece.color == me:
        text, squares = f"They threaten to take your {NAMES[victim_piece.piece_type]} on {to} with the {attacker}.", [to]
    elif kind == "fork":
        after_threat = passed.copy(stack=False)
        after_threat.push(move)
        hit = _forks(after_threat, move.to_square, me)
        if len(hit) < 2:
            return None
        text, squares = f"They threaten a fork: the {attacker} to {to} would attack your {' and '.join(hit[:2])}.", [to]
    elif kind == "discovered" and (found := _uncovered(passed, move, me)):
        text, squares = f"Moving their {attacker} would uncover an attack on your {found[1]}.", [chess.square_name(found[0])]
    else:
        text, squares = f"They threaten to win material with the {attacker} to {to}.", []
    mine = _mark(1, text, [_their(uci)], squares)
    victim_name = _name(board, victim_sq) if kind in ("capture", "mate") else None
    better = None
    if victim_name:
        between = chess.SquareSet(chess.between(move.from_square, move.to_square))
        better = _fix(board, drill, victim_sq, move.from_square, uci, victim_name, attacker, path=between)
    return {"mine": mine, "better": better}


def _free(board: chess.Board, drill: dict, ev: dict) -> dict | None:
    caps = [c["uci"] for c in ev.get("free_captures", [])]
    if not caps:
        return None
    pick = next((u for u in drill["accepted"] if u in caps), caps[0])
    move = chess.Move.from_uci(pick)
    attacker, victim = _name(board, move.from_square), _name(board, move.to_square)
    if attacker is None or victim is None:
        return None
    to = chess.square_name(move.to_square)
    mine = _mark(0, f"You could win their {victim} on {to} with your {attacker}.", [{"from": pick[:2], "to": pick[2:4], "tone": "better"}], [to])
    better = _mark(1, f"This wins the {victim} on {to}.", [], [to]) if drill["accepted"] and drill["accepted"][0] in caps else None
    return {"mine": mine, "better": better}


def build(cause: str, drill: dict, evidence: dict, alternatives: list[str] | None = None) -> dict | None:
    """The why for one drill, or None when the cause has none or the record does not fit the board."""
    board = chess.Board(drill["fen"])
    try:
        if cause == "hanging_own":
            return _hanging(board, drill, evidence, alternatives or [])
        if cause == "threat":
            return _threat(board, drill, evidence)
        if cause == "missed_free":
            return _free(board, drill, evidence)
    except (KeyError, ValueError, IndexError, TypeError):
        return None  # a record that does not fit the board: no sentence rather than a wrong one
    return None
