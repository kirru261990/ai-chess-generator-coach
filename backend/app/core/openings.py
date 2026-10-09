"""A starter opening book: well-known opening lines, so the page can label a move "Book".

This is deliberately small (about 60 mainline systems, to move 6 to 10) and is NOT a full opening database: a move that is
not in it is simply not labelled, which says nothing about its quality. Lines are SAN strings from the standard start.
Every position reached by every line counts as book (transpositions included), keyed by the position without move counters.
Replacing this with a complete list (for example the CC0 lichess-org/chess-openings tables) only needs `LINES` to change;
the licence row goes in THIRD_PARTY.md if that data is added.
"""

from __future__ import annotations

import chess

MAX_BOOK_PLY = 30  # a move later than this is never labelled book

LINES: list[tuple[str, str]] = [
    # 1.e4 e5
    ("Ruy Lopez: Closed", "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3"),
    ("Ruy Lopez: Berlin Defense", "e4 e5 Nf3 Nc6 Bb5 Nf6 O-O Nxe4 d4 Nd6 Bxc6 dxc6 dxe5 Nf5 Qxd8+ Kxd8"),
    ("Italian Game: Giuoco Pianissimo", "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6 O-O O-O"),
    ("Italian Game: Giuoco Piano", "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d4 exd4 cxd4 Bb4+ Nc3 Nxe4"),
    ("Italian Game: Two Knights Defense", "e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Be7 O-O O-O"),
    ("Evans Gambit", "e4 e5 Nf3 Nc6 Bc4 Bc5 b4 Bxb4 c3 Ba5 d4 exd4 O-O d6 cxd4 Bb6"),
    ("Scotch Game", "e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nf6 Nxc6 bxc6 e5 Qe7 Qe2 Nd5 c4 Ba6"),
    ("Petrov's Defense", "e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d4 d5 Bd3 Nc6 O-O Be7"),
    ("Philidor Defense", "e4 e5 Nf3 d6 d4 Nf6 Nc3 Nbd7 Bc4 Be7"),
    ("Four Knights Game", "e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5 Bb4 O-O O-O d3 d6"),
    ("Ponziani Opening", "e4 e5 Nf3 Nc6 c3 Nf6 d4 Nxe4 d5 Ne7 Nxe5 Ng6"),
    ("Vienna Game", "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3 Be7"),
    ("King's Gambit", "e4 e5 f4 exf4 Nf3 g5 h4 g4 Ne5 Nf6"),
    ("Danish Gambit", "e4 e5 d4 exd4 c3 dxc3 Bc4 cxb2 Bxb2 d5 Bxd5 Nf6 Bxf7+ Kxf7 Qxd8 Bb4+ Qd2 Bxd2+ Nxd2"),
    ("Bishop's Opening", "e4 e5 Bc4 Nf6 d3 c6 Nf3 d5 Bb3 Bd6"),
    # 1.e4 Sicilian
    ("Sicilian Defense: Najdorf", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be3 e5 Nb3 Be6 f3 Be7 Qd2 O-O O-O-O"),
    ("Sicilian Defense: Dragon", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6 Be3 Bg7 f3 O-O Qd2 Nc6"),
    ("Sicilian Defense: Scheveningen", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 e6 Be2 Be7 O-O O-O f4 Nc6 Be3 Bd7"),
    ("Sicilian Defense: Classical", "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 d6 Bg5 e6 Qd2 a6 O-O-O Bd7 f4 b5"),
    ("Sicilian Defense: Sveshnikov", "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 e5 Ndb5 d6 Bg5 a6 Na3 b5 Nd5 Be7"),
    ("Sicilian Defense: Taimanov", "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6 Nc3 Qc7 Be3 a6 Qd2 Nf6 O-O-O Bb4"),
    ("Sicilian Defense: Kan", "e4 c5 Nf3 e6 d4 cxd4 Nxd4 a6 Bd3 Bc5 Nb3 Ba7 O-O Ne7"),
    ("Sicilian Defense: Alapin", "e4 c5 c3 Nf6 e5 Nd5 d4 cxd4 Nf3 Nc6 cxd4 d6 Bc4 Nb6 Bb3 dxe5 Nxe5 Nxe5 dxe5 Qxd1+ Kxd1"),
    ("Sicilian Defense: Closed", "e4 c5 Nc3 Nc6 g3 g6 Bg2 Bg7 d3 d6 Be3 e6 Qd2 Nd4"),
    ("Sicilian Defense: Grand Prix Attack", "e4 c5 Nc3 Nc6 f4 g6 Nf3 Bg7 Bc4 e6 f5 Nge7"),
    ("Sicilian Defense: Smith-Morra Gambit", "e4 c5 d4 cxd4 c3 dxc3 Nxc3 Nc6 Nf3 d6 Bc4 e6 O-O Nf6 Qe2 Be7 Rd1 e5"),
    # other 1.e4
    ("French Defense: Classical", "e4 e6 d4 d5 Nc3 Nf6 Bg5 Be7 e5 Nfd7 Bxe7 Qxe7 f4 O-O Nf3 c5"),
    ("French Defense: Advance", "e4 e6 d4 d5 e5 c5 c3 Nc6 Nf3 Qb6 a3 Nh6 b4 cxd4 cxd4 Nf5"),
    ("French Defense: Tarrasch", "e4 e6 d4 d5 Nd2 Nf6 e5 Nfd7 Bd3 c5 c3 Nc6 Ne2 cxd4 cxd4 f6"),
    ("French Defense: Winawer", "e4 e6 d4 d5 Nc3 Bb4 e5 c5 a3 Bxc3+ bxc3 Ne7 Qg4 Qc7 Qxg7 Rg8 Qxh7 cxd4 Ne2 Nbc6 f4 Bd7"),
    ("Caro-Kann Defense: Classical", "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 h4 h6 Nf3 Nd7 h5 Bh7 Bd3 Bxd3 Qxd3 e6"),
    ("Caro-Kann Defense: Advance", "e4 c6 d4 d5 e5 Bf5 Nf3 e6 Be2 Nd7 O-O Ne7"),
    ("Scandinavian Defense", "e4 d5 exd5 Qxd5 Nc3 Qa5 d4 Nf6 Nf3 c6 Bc4 Bf5 Bd2 e6 Qe2 Bb4"),
    ("Pirc Defense", "e4 d6 d4 Nf6 Nc3 g6 Nf3 Bg7 Be2 O-O O-O"),
    ("Alekhine's Defense", "e4 Nf6 e5 Nd5 d4 d6 Nf3 Bg4 Be2 e6 O-O Be7 c4 Nb6"),
    ("Modern Defense", "e4 g6 d4 Bg7 Nc3 d6 Nf3 Nf6 Be2 O-O O-O"),
    # 1.d4
    ("Queen's Gambit Declined", "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6 Bh4 b6 cxd5 Nxd5 Bxe7 Qxe7"),
    ("Queen's Gambit Accepted", "d4 d5 c4 dxc4 Nf3 Nf6 e3 e6 Bxc4 c5 O-O a6 Qe2 b5 Bb3 Bb7 Rd1 Nbd7 Nc3 Qb6"),
    ("Slav Defense", "d4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4 a4 Bf5 e3 e6 Bxc4 Bb4 O-O Nbd7 Qe2 Bg6"),
    ("Semi-Slav Defense", "d4 d5 c4 c6 Nf3 Nf6 Nc3 e6 e3 Nbd7 Bd3 dxc4 Bxc4 b5 Bd3 Bb7 O-O a6 e4 c5"),
    ("London System", "d4 d5 Bf4 Nf6 e3 c5 c3 Nc6 Nd2 e6 Ngf3 Bd6 Bg3 O-O Bd3 b6"),
    ("London System: vs ...Nf6 and ...e6", "d4 Nf6 Bf4 e6 e3 Be7 Nf3 O-O h3 b6 Bd3 Bb7 Nbd2 c5 c3 d6"),
    ("Colle System", "d4 d5 Nf3 Nf6 e3 e6 Bd3 c5 b3 Nc6 O-O Bd6 Bb2 O-O Nbd2 b6"),
    ("Queen's Gambit: Orthodox setup", "d4 d5 Nf3 Nf6 c4 e6 Nc3 Be7 Bf4 O-O e3"),
    ("King's Indian Defense", "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7 Ne1 Nd7 Be3 f5"),
    ("Nimzo-Indian Defense", "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5 O-O Nc6 a3 Bxc3 bxc3 dxc4 Bxc4 Qc7"),
    ("Queen's Indian Defense", "d4 Nf6 c4 e6 Nf3 b6 g3 Bb7 Bg2 Be7 O-O O-O Nc3 Ne4 Qc2 Nxc3 Qxc3 c5"),
    ("Catalan Opening", "d4 Nf6 c4 e6 g3 d5 Bg2 Be7 Nf3 O-O O-O dxc4 Qc2 a6 Qxc4 b5 Qc2 Bb7"),
    ("Grunfeld Defense", "d4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5 e4 Nxc3 bxc3 Bg7 Nf3 c5 Rb1 O-O Be2"),
    ("Benoni Defense", "d4 Nf6 c4 c5 d5 e6 Nc3 exd5 cxd5 d6 e4 g6 Nf3 Bg7 Be2 O-O O-O Re8"),
    ("Budapest Gambit", "d4 Nf6 c4 e5 dxe5 Ng4 Bf4 Nc6 Nf3 Bb4+ Nbd2 Qe7 e3 Ngxe5 Nxe5 Nxe5"),
    ("Dutch Defense", "d4 f5 g3 Nf6 Bg2 e6 Nf3 Be7 O-O O-O c4 d6 Nc3 Qe8"),
    ("Trompowsky Attack", "d4 Nf6 Bg5 Ne4 Bf4 c5 f3 Qa5+ c3 Nf6 d5 Qb6 Qc1"),
    # flank openings
    ("English Opening", "c4 e5 Nc3 Nf6 Nf3 Nc6 g3 d5 cxd5 Nxd5 Bg2 Nb6 O-O Be7 d3 O-O"),
    ("English Opening: Symmetrical", "c4 c5 Nf3 Nf6 Nc3 Nc6 g3 g6 Bg2 Bg7 O-O O-O d4 cxd4 Nxd4 d6"),
    ("Reti Opening", "Nf3 d5 g3 Nf6 Bg2 e6 O-O Be7 d3 O-O Nbd2 c5 e4 Nc6 c3 b5"),
    ("Bird Opening", "f4 d5 Nf3 Nf6 e3 g6 Be2 Bg7 O-O O-O d3 c5"),
    ("Larsen's Opening", "b3 e5 Bb2 Nc6 e3 d5 Bb5 Bd6 f4 Qh4+ g3"),
]

_book: dict[str, str] | None = None
FIRST_MOVE_NAMES = {  # the general name for a position that several different openings share
    "e4": "King's Pawn Opening", "d4": "Queen's Pawn Opening", "c4": "English Opening",
    "Nf3": "Reti Opening", "f4": "Bird Opening", "b3": "Larsen's Opening",
}


def _key(board: chess.Board) -> str:
    return board.epd()  # the position without move counters


def _family(name: str) -> str:
    return name.split(":")[0]


def book() -> dict[str, str]:
    """Position key -> opening name, for every position on every line (built once).

    A position reached by lines of one family (for example two Ruy Lopez variations) gets the family name; a position shared
    by different families (for example everything after 1.e4) gets the general name for the first move.
    """
    global _book
    if _book is None:
        names: dict[str, set[str]] = {}
        firsts: dict[str, str] = {}
        for name, line in LINES:
            board = chess.Board()
            for i, san in enumerate(line.split()):
                if i == 0:
                    first = san
                board.push_san(san)
                key = _key(board)
                names.setdefault(key, set()).add(name)
                firsts.setdefault(key, first)
        table: dict[str, str] = {}
        for key, found in names.items():
            if len(found) == 1:
                table[key] = next(iter(found))
                continue
            families = {_family(n) for n in found}
            table[key] = families.pop() if len(families) == 1 else FIRST_MOVE_NAMES.get(firsts[key], "Opening")
        _book = table
    return _book


def book_name(board_after: chess.Board, plies_played: int) -> str | None:
    """The opening this position belongs to, or None. `plies_played` = half-moves played so far (early moves only)."""
    if plies_played < 1 or plies_played > MAX_BOOK_PLY:
        return None
    return book().get(_key(board_after))
