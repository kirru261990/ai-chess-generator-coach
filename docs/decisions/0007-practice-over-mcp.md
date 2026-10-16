# ADR 0007: Practice mode as MCP tools for chat clients

**Status:** Accepted 2026-10-16 · **Decided by:** the owner (reachable from their Mac with a login; ChatGPT Plus to be tried; practice
only), on Claude's plan in `docs/mcp-practice-plan.md`
**Related:** spec C4, PRD v2 §11, ADR 0005, ADR 0006, AGENTS rules 1, 2 and 4

| # | Decision | Why | To reverse |
|---|---|---|---|
| 1 | The tools are **practice only**. No tool starts or takes a starting or delayed test. | A chat assistant can talk about a position, so a test taken through it would not be unassisted (rule 4). | Add test tools only with a design for keeping them unassisted. |
| 2 | One remote server on the owner's Mac behind a tunnel, **OAuth with one password** (`app/mcp/auth.py`). | Claude and ChatGPT accept only a remote HTTPS address, with OAuth or none. The data stays on the Mac. | A hosted server moves the games off the Mac. |
| 3 | The tools call `learner/practice.py`, `progress.py` and `assessment.py` unchanged; the tool layer renders text and decides nothing. | PRD §11: no second scoring path. | n/a |
| 4 | **The store-import guard** (`test_only_the_coach_routes_reach_the_position_store`) now also allows `mcp/practice_tools.py` and `mcp/server.py`. | The guard predates this plan and allowed only `api/coach.py`. The chat tools are the second client of the same service. | Route the tools through an `api/` module and restore the guard. |
| 5 | The `get_game` skeleton MCP tool is retired. Its parity test now checks `tools.get_game` against the API. | It read the web API's in-memory games, which a separate process cannot see, and it is not practice. | Re-register it in `server.py`. |
| 6 | Plain-text boards (a code block, `[x]` marks, a FEN and a piece list). | Works in every client with no image support and no new dependency. | A board picture needs a renderer and a `THIRD_PARTY.md` row. |
| 7 | Tokens are bound to this server (`validate_token_resource`); one scope, `practice`, whatever a client asks for; secrets stored as SHA-256 hashes; scrypt password; 5 wrong tries lock 15 minutes (global, persisted). | One owner, a public address: refuse a look-alike client, a stolen database and guessing. | Constants in `auth.py`. |
| 8 | The server instructions tell the chat model to only relay the tools and never analyse or answer first. | Keeps "what the engine verified" apart from what the model says. It is guidance, not enforcement, and the docs say so. | n/a |
| 9 | Practice from chat is saved in the owner's real store like web practice (always assisted). No model call is made by this server, so there is no spend. | Same loop, second surface. | n/a |

Known limits: the library's `/revoke` asks for a client secret, so clients registered without one cannot revoke through it (they
can still expire); ChatGPT Plus may refuse the tools that change data (unconfirmed, see `docs/mcp-setup.md`); the Mac must be on
and the tunnel running.
