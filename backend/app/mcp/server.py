"""MCP server over the shared tool layer. Owns no game state of its own."""

from mcp.server.mcpserver import MCPServer

from app.api import tools

mcp = MCPServer("chess-coach")


@mcp.tool()
def get_game(game_id: str) -> dict:
    """Return the current state of a game (FEN, moves, revision, outcome, assisted flag)."""
    return tools.get_game(game_id)


if __name__ == "__main__":
    mcp.run()
