"""MCP server for practice mode (docs/mcp-practice-plan.md §4 to §7). Owns no chess or scoring logic: each tool opens the store,
calls `practice_tools` (which calls the same service layer as the web app) and returns its text.

Practice only. No tool starts or takes a test, so a chat assistant cannot help with an unassisted test (AGENTS rule 4). The old
`get_game` skeleton tool is retired: it read the web API's in-memory games, which this separate process cannot see, and it is
not practice.

    python -m app.mcp.server stdio    # Claude Desktop / Claude Code on this Mac (no login needed locally)
    python -m app.mcp.server http     # remote clients behind a tunnel; needs the login (not built yet: refuses to start)
"""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Callable
from contextlib import contextmanager

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from app.db.schema import connect
from app.engine.evidence import open_evidence
from app.mcp import practice_tools as T

NAME = "chess-coach"

INSTRUCTIONS = (
    "This server runs Replay My Mistakes practice from the player's own games. You only relay it. Never analyse the position, "
    "suggest a move, or say whether an answer is right before the tool does. Never call practice_hint unless the player asks "
    "for a hint. Show each tool's text exactly as it is, including the board. Only the tools check chess facts; do not add "
    "chess claims of your own. Practice is always assisted. The starting and delayed tests are taken in the web app only."
)

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

ConnFactory = Callable[[], sqlite3.Connection]


def build_server(conn_factory: ConnFactory = connect, opener=open_evidence, **server_args) -> MCPServer:
    """The server. `conn_factory` and `opener` are replaced by scripted ones in tests. Each call gets its own connection and the
    engine (for a move check) is started inside the call only."""
    mcp = MCPServer(NAME, instructions=INSTRUCTIONS, **server_args)

    @contextmanager
    def store():
        conn = conn_factory()
        try:
            yield conn
        finally:
            conn.close()

    @mcp.tool(annotations=READ)
    def practice_status() -> str:
        """Show which practice types are ready, locked or in progress, and when the delayed test opens. Changes nothing."""
        with store() as c:
            return T.practice_status(c)

    @mcp.tool(annotations=WRITE)
    def practice_start(mistake_type: str) -> str:
        """Start a practice session, or resume the open one, and show position 1. mistake_type: pieces_in_danger or free_pieces. Saves progress."""
        with store() as c:
            return T.practice_start(c, mistake_type)

    @mcp.tool(annotations=READ)
    def practice_show(session_id: int) -> str:
        """Show the current position and what to do next. Safe to call again. Changes nothing."""
        with store() as c:
            return T.practice_show(c, session_id)

    @mcp.tool(annotations=WRITE)
    def practice_answer(session_id: int, square: str) -> str:
        """Step 1, the question: give the square of the piece (for example g5), or "none" for no immediate threat. Saves the answer."""
        with store() as c:
            return T.practice_answer(c, session_id, square)

    @mcp.tool(annotations=WRITE)
    def practice_move(session_id: int, move: str) -> str:
        """Step 2: make a move, like Nf3, Bxe5, O-O or g1f3. The engine checks it (about 2 seconds) and the feedback follows. Saves the attempt."""
        with store() as c:
            return T.practice_move(c, session_id, move, opener)

    @mcp.tool(annotations=WRITE)
    def practice_hint(session_id: int) -> str:
        """Give the next of three hints. Only when the player asks. Marks this try as assisted."""
        with store() as c:
            return T.practice_hint(c, session_id)

    @mcp.tool(annotations=WRITE)
    def practice_retry(session_id: int) -> str:
        """After the feedback: try the same position again as a new try."""
        with store() as c:
            return T.practice_retry(c, session_id)

    @mcp.tool(annotations=WRITE)
    def practice_next(session_id: int) -> str:
        """After the feedback: go to the next position. After the last one the session finishes and the delayed test is scheduled."""
        with store() as c:
            return T.practice_next(c, session_id)

    @mcp.tool(annotations=READ)
    def practice_summary(session_id: int) -> str:
        """Show the summary of a finished session and when its delayed test opens. Changes nothing."""
        with store() as c:
            return T.practice_summary(c, session_id)

    @mcp.tool(annotations=READ)
    def progress() -> str:
        """Show test scores and assisted practice, kept apart, with denominators. Changes nothing."""
        with store() as c:
            return T.progress(c)

    return mcp


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else ""
    if mode == "stdio":
        build_server().run("stdio")
        return 0
    if mode == "http":
        print("http mode needs the login (app/mcp/auth.py), which is not built yet; it refuses to start without it.",
              file=sys.stderr)
        return 2
    print("usage: python -m app.mcp.server stdio|http", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
