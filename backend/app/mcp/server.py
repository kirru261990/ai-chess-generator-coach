"""MCP server for practice mode (docs/mcp-practice-plan.md §4 to §7). Owns no chess or scoring logic: each tool opens the store,
calls `practice_tools` (which calls the same service layer as the web app) and returns its text.

Practice only. No tool starts or takes a test, so a chat assistant cannot help with an unassisted test (AGENTS rule 4). The old
`get_game` skeleton tool is retired: it read the web API's in-memory games, which this separate process cannot see, and it is
not practice.

    python -m app.mcp.server stdio    # Claude Desktop / Claude Code on this Mac (no login needed locally)
    python -m app.mcp.server http     # remote clients behind a tunnel; needs MCP_PUBLIC_URL and a password (python -m app.mcp.setup)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from mcp.server.apps import Apps
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from app.db.schema import connect
from app.engine.evidence import open_evidence
from app.learner import assessment as A
from app.mcp import auth
from app.mcp import game_tools as G
from app.mcp import practice_tools as T

log = logging.getLogger(__name__)

NAME = "chess-coach"

BOARD_URI = "ui://chess-coach/board.html"
BOARD_HTML_PATH = Path(__file__).parent / "ui" / "board.html"  # built from web/ (`pnpm build:mcp`); see docs/mcp-app-board.md
BOARD_MISSING = ("<!doctype html><meta charset=utf-8><p style=\"font:14px system-ui;padding:12px\">The interactive board has not been "
                 "built. Run <code>pnpm build:mcp</code> in web/. The text board in the chat still works.</p>")

INSTRUCTIONS = (
    "This server runs Replay My Mistakes practice from the player's own games. You only relay it. Never analyse the position, "
    "suggest a move, or say whether an answer is right before the tool does. Never call practice_hint unless the player asks "
    "for a hint. Show each tool's text exactly as it is, including the board. Only the tools check chess facts; do not add "
    "chess claims of your own. Practice is always assisted. The starting and delayed tests are taken in the web app only. "
    "The game_ tools play a game against Stockfish, either Play (no help) or Practice (assisted). In a Play game never say whether "
    "a move is good or bad, never suggest a move, and never mention threats, hints or the evaluation; only report the tool's "
    "text. Call game_hint, game_undo or game_threats only when the player asks, and never in a Play game. Chat games are kept in "
    "memory only and are not saved. game_apply_move and game_engine_move belong to the board page: never call them."
)

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

ConnFactory = Callable[[], sqlite3.Connection]


def build_server(conn_factory: ConnFactory = connect, opener=open_evidence, **server_args) -> MCPServer:
    """The server. `conn_factory` and `opener` are replaced by scripted ones in tests. Each call gets its own connection and the
    engine (for a move check) is started inside the call only."""

    @contextmanager
    def store():
        conn = conn_factory()
        try:
            yield conn
        finally:
            conn.close()

    def board(text: str, c: sqlite3.Connection, session_id: int | None = None) -> CallToolResult:
        """The tool's text (always shown, and all a client without app support gets) plus, for the interactive board, the same
        session data the web page uses. A refused step is text only."""
        plain = CallToolResult(content=[TextContent(type="text", text=text)])
        sid = session_id if session_id is not None else T.session_id_of(text)
        if T.is_refusal(text) or sid is None:
            return plain
        try:
            data = T.payload(c, sid)
        except (sqlite3.Error, A.AssessmentError, ValueError, KeyError):  # the board is an extra: never lose the text for it
            log.exception("could not build the board data")
            return plain
        return CallToolResult(content=[TextContent(type="text", text=text)], structured_content=data)

    # Tools that show a board are bound to the interactive board (MCP Apps). They must be declared before the server is built.
    apps = Apps()
    html = BOARD_HTML_PATH.read_text(encoding="utf-8") if BOARD_HTML_PATH.exists() else BOARD_MISSING
    apps.add_html_resource(BOARD_URI, html, name="chess-board", title="Practice board",
                           description="The interactive practice board (the same board as the web app).", prefers_border=True)
    ui = {"resource_uri": BOARD_URI, "meta": {"openai/outputTemplate": BOARD_URI}}  # the second key is for ChatGPT's own loader

    @apps.tool(annotations=WRITE, **ui)
    def practice_start(mistake_type: str) -> CallToolResult:
        """Start a practice session, or resume the open one, and show position 1. mistake_type: pieces_in_danger or free_pieces. Saves progress."""
        with store() as c:
            return board(T.practice_start(c, mistake_type), c)

    @apps.tool(annotations=WRITE, **ui)
    def practice_show(session_id: int) -> CallToolResult:
        """Show the current position and what to do next. Safe to call again. The first view of a new session saves its first attempt."""
        with store() as c:
            return board(T.practice_show(c, session_id), c, session_id)

    @apps.tool(annotations=WRITE, **ui)
    def practice_answer(session_id: int, square: str, expected_ord: int | None = None) -> CallToolResult:
        """Step 1, the question: give the square of the piece (for example g5), or "none" for no immediate threat. Saves the answer."""
        with store() as c:
            return board(T.practice_answer(c, session_id, square, expected_ord), c, session_id)

    @apps.tool(annotations=WRITE, **ui)
    def practice_move(session_id: int, move: str, expected_ord: int | None = None) -> CallToolResult:
        """Step 2: make a move, like Nf3, Bxe5, O-O or g1f3. The engine checks it (about 2 seconds) and the feedback follows. Saves the attempt."""
        with store() as c:
            return board(T.practice_move(c, session_id, move, opener, expected_ord), c, session_id)

    @apps.tool(annotations=WRITE, **ui)
    def practice_hint(session_id: int, expected_ord: int | None = None) -> CallToolResult:
        """Give the next of three hints. Only when the player asks. Marks this try as assisted."""
        with store() as c:
            return board(T.practice_hint(c, session_id, expected_ord), c, session_id)

    @apps.tool(annotations=WRITE, **ui)
    def practice_retry(session_id: int, expected_ord: int | None = None) -> CallToolResult:
        """After the feedback: try the same position again as a new try."""
        with store() as c:
            return board(T.practice_retry(c, session_id, expected_ord), c, session_id)

    @apps.tool(annotations=WRITE, **ui)
    def practice_next(session_id: int, expected_ord: int | None = None) -> CallToolResult:
        """After the feedback: go to the next position. After the last one the session finishes and the delayed test is scheduled."""
        with store() as c:
            return board(T.practice_next(c, session_id, expected_ord), c, session_id)

    def game_board(pair) -> CallToolResult:
        """A game tool's (data, text) as a result: the text always, and the board data unless the step was refused."""
        structured, words = pair
        return CallToolResult(content=[TextContent(type="text", text=words)], structured_content=structured)

    @apps.tool(annotations=WRITE, **ui)
    def game_new(color: str = "white", level: int = 3, mode: str = "play") -> CallToolResult:
        """Start a game against Stockfish and show the board. color: white or black. level: 1 to 10. mode: play (no help) or practice (assisted: verdicts, hints, undo, threat arrows)."""
        return game_board(G.game_new(color, level, mode))

    @apps.tool(annotations=WRITE, **ui)
    def game_show(game_id: str) -> CallToolResult:
        """Show the board of a game and whose turn it is. Safe to call again. If Stockfish owes a reply it plays it."""
        return game_board(G.game_show(game_id))

    @apps.tool(annotations=WRITE, **ui)
    def game_move(game_id: str, move: str, expected_revision: int | None = None) -> CallToolResult:
        """Play your move, like Nf3, exd5, O-O or g1f3. Stockfish replies in the same call (about a second)."""
        return game_board(G.game_move(game_id, move, expected_revision))

    app_only = {"resource_uri": BOARD_URI, "visibility": ["app"], "meta": {"openai/outputTemplate": BOARD_URI}}  # the board's own steps

    @apps.tool(annotations=WRITE, **app_only)
    def game_apply_move(game_id: str, move: str, expected_revision: int) -> CallToolResult:
        """For the board only, not for the model: play the player's move without Stockfish's reply, so the board can show it first."""
        return game_board(G.game_move(game_id, move, expected_revision, reply=False))

    @apps.tool(annotations=WRITE, **app_only)
    def game_engine_move(game_id: str, expected_revision: int) -> CallToolResult:
        """For the board only, not for the model: Stockfish's reply to the move just shown. Plays nothing if the board is out of date."""
        return game_board(G.game_engine_move(game_id, expected_revision))

    @apps.tool(annotations=WRITE, **ui)
    def game_resign(game_id: str) -> CallToolResult:
        """Resign the game. It ends at once."""
        return game_board(G.game_resign(game_id))

    @apps.tool(annotations=WRITE, **ui)
    def game_undo(game_id: str) -> CallToolResult:
        """Practice games only, and only when the player asks: take back the last move. The game stays assisted."""
        return game_board(G.game_undo(game_id))

    @apps.tool(annotations=WRITE, **ui)
    def game_hint(game_id: str, level: int = 1) -> CallToolResult:
        """Practice games only, and only when the player asks: hint steps 1 to 5 for the position (5 is the move itself)."""
        return game_board(G.game_hint(game_id, level))

    @apps.tool(annotations=WRITE, **ui)
    def game_threats(game_id: str, show: bool = True) -> CallToolResult:
        """Practice games only: turn the threat arrows on the board on or off."""
        return game_board(G.game_threats(game_id, show))

    mcp = MCPServer(NAME, instructions=INSTRUCTIONS, extensions=[apps], **server_args)

    @mcp.tool(annotations=READ)
    def practice_status() -> str:
        """Show which practice types are ready, locked or in progress, and when the delayed test opens. Changes nothing."""
        with store() as c:
            return T.practice_status(c)

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


DEFAULT_PORT = 8765
BROWSER_ORIGINS = ["https://claude.ai", "https://claude.com", "https://chatgpt.com", "https://chat.openai.com"]


class HostGuard:
    """Refuse any request whose Host header is not ours, on every route (the library checks only the /mcp endpoint). Defends
    against DNS rebinding and against the tunnel being reached under another name."""

    def __init__(self, app, allowed_hosts: set[str]):
        self.app, self.allowed = app, {h.lower() for h in allowed_hosts}

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            host = dict(scope["headers"]).get(b"host", b"").decode("latin-1").lower()
            if host not in self.allowed:
                if scope["type"] == "http":
                    await send({"type": "http.response.start", "status": 421, "headers": [(b"content-type", b"text/plain")]})
                    await send({"type": "http.response.body", "body": b"misdirected request"})
                return
        await self.app(scope, receive, send)


class MethodLog:
    """Log each JSON-RPC method (and tool name) of a POST, e.g. `mcp tools/call practice_start`, so a client's behaviour (does it ask for
    the board resource?) can be seen in the server's output. Names only: arguments and results are never logged."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        chunks: list[dict] = []
        while True:
            message = await receive()
            chunks.append(message)
            if message["type"] != "http.request" or not message.get("more_body"):
                break
        try:
            body = json.loads(b"".join(m.get("body", b"") for m in chunks) or b"null")
            for call in body if isinstance(body, list) else [body]:
                name = (call.get("params") or {}).get("name") or (call.get("params") or {}).get("uri") or ""
                log.info("mcp %s %s", call.get("method"), name)
        except (ValueError, AttributeError):
            pass
        replay = iter(chunks)

        async def replayed():
            return next(replay, {"type": "http.disconnect"})

        await self.app(scope, replayed, send)


def build_http_app(public_url: str, *, auth_path=None, conn_factory: ConnFactory = connect, opener=open_evidence,
                   port: int = DEFAULT_PORT, clock: Callable[[], float] = time.time):
    """The remote app: the tools behind OAuth, the login page, and the host checks. Returns (ASGI app, provider)."""
    public_url = public_url.rstrip("/")
    provider = auth.PracticeAuthProvider(public_url, auth_path, clock)
    settings = AuthSettings(
        issuer_url=public_url, resource_server_url=public_url + "/mcp", validate_token_resource=True,
        client_registration_options=ClientRegistrationOptions(enabled=True, default_scopes=[auth.SCOPE]),
        revocation_options=RevocationOptions(enabled=True), required_scopes=[auth.SCOPE])
    mcp = build_server(conn_factory, opener, auth_server_provider=provider, auth=settings)
    auth.register_login(mcp, provider)
    hosts = {urlparse(public_url).netloc, f"127.0.0.1:{port}", f"localhost:{port}"}
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=sorted(hosts),
                                         allowed_origins=[public_url, *BROWSER_ORIGINS])
    app = mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=security)
    return HostGuard(MethodLog(app), hosts), provider


def _run_http() -> int:
    public = os.environ.get("MCP_PUBLIC_URL", "").strip().rstrip("/")
    port = int(os.environ.get("MCP_PORT", DEFAULT_PORT))
    host = urlparse(public).hostname
    if not public or not (public.startswith("https://") or host in auth.LOCAL_HOSTS):
        print("Set MCP_PUBLIC_URL in .env to the tunnel's https address (no trailing path).", file=sys.stderr)
        return 2
    if not auth.password_is_set(auth.connect()):
        print("No password is set. Run: python -m app.mcp.setup", file=sys.stderr)
        return 2
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app, _ = build_http_app(public, port=port)
    uvicorn.run(app, host="127.0.0.1", port=port, proxy_headers=False, server_header=False)
    return 0


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else ""
    if mode == "stdio":
        build_server().run("stdio")
        return 0
    if mode == "http":
        return _run_http()
    print("usage: python -m app.mcp.server stdio|http", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
