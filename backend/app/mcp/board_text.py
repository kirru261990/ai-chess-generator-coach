"""Plain-text boards for chat clients (no picture support needed). Words only: this module draws what it is given and decides
nothing about the position (AGENTS rule 1)."""

from __future__ import annotations

from collections.abc import Iterable

import chess

_GLYPH = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
}
_ORDER = "KQRBN"


def render_board(fen: str, side: str = "white", marks: Iterable[str] = ()) -> str:
    """The board drawn from `side`'s point of view. Squares in `marks` are shown as [x]; others as ' x '. White pieces are the
    outlined glyphs, black the filled ones."""
    board = chess.Board(fen)
    marked = {chess.parse_square(m) for m in marks}
    white = side != "black"
    files = range(8) if white else range(7, -1, -1)
    ranks = range(7, -1, -1) if white else range(8)
    header = "    " + "  ".join(chess.FILE_NAMES[f] for f in files)
    lines = [header]
    for r in ranks:
        cells = []
        for f in files:
            sq = chess.square(f, r)
            piece = board.piece_at(sq)
            glyph = _GLYPH[piece.symbol()] if piece else "·"
            cells.append(f"[{glyph}]" if sq in marked else f" {glyph} ")
        lines.append(f"{r + 1} {''.join(cells)} {r + 1}")
    lines.append(header)
    return "\n".join(lines)


def piece_list(fen: str, color: str) -> str:
    """One side's pieces in words, e.g. 'Kg1, Qd1, Ra1, Rh1, pawns a2 b2 c2'. For plain-text and screen-reader clients."""
    board = chess.Board(fen)
    c = chess.WHITE if color == "white" else chess.BLACK
    parts = []
    for letter in _ORDER:
        pt = chess.Piece.from_symbol(letter).piece_type
        for sq in sorted(board.pieces(pt, c)):
            parts.append(f"{letter}{chess.square_name(sq)}")
    pawns = sorted(board.pieces(chess.PAWN, c))
    if pawns:
        parts.append("pawns " + " ".join(chess.square_name(sq) for sq in pawns))
    return ", ".join(parts)
