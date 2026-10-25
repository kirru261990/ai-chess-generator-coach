# 0010 — An open, games-only version of the chat connector

Status: accepted, 2026-10-25. Builds on ADR 0007 (practice over MCP) and ADR 0009 (games over MCP).

## Decision

`python -m app.mcp.server public` serves only the `game_` tools (Play and assisted Practice games against Stockfish) with no login.

- **No stored data.** No SQLite, no learner store, no auth database. Games live in memory, are forgotten after 2 hours idle, at most 500 are held, and nothing is linked to a person (no account, no IP kept; the log holds method and tool names only).
- **No cost to the owner.** The tools use Stockfish and `python-chess` only. No Anthropic or other model call is reachable (a test makes any such call fail). Each user's chat tokens are paid by their own Claude plan. Hosting must be a free tier.
- **Not exposed:** `practice_*` (Replay My Mistakes) and `progress` read the owner's own games and tests, so they exist only in the private server. The tests stay in the web app.
- **Bounded:** one request budget for the whole service (600 a minute, then HTTP 429), because every caller arrives from the chat provider's addresses and a per-address limit would mean nothing. Stockfish is one shared process.
- The ADR 0005 rule is unchanged: no help of any kind in Play.

## Hosting and clients (added 2026-10-25)

- **Host:** Render free web service built from the root `Dockerfile` (Hugging Face Docker Spaces turned out to be paid). `https://chess-coach-public.onrender.com/mcp`, privacy page `/privacy`, health `/healthz`. Deploys are manual (no webhook: the service was made from the public repo address).
- **Awake hours:** a GitHub Actions schedule (`.github/workflows/keep-awake.yml`) visits `/healthz` from 05:00 to 23:20 IST; the instance sleeps the rest of the night. A free UptimeRobot monitor exists but is paused (it cannot be limited to hours on the free plan).
- **Clients tried:** claude.ai in a browser (works once the board page was shrunk from 562 KB to 330 KB; the SDK's client and schema libraries were replaced by `web/src/mcp-board/miniApp.ts`), ChatGPT Plus (works, board and larger view), Claude Desktop app (board not drawn: open Claude bug, ext-apps issue 671; text and moves only).
- **Board text:** the open server's tool text has no letter board (the page draws it); the private server keeps it.

## Why not the private server with a shared password

That server holds the owner's practice data and makes attempts that count toward their progress; anyone who signs in can read and change it.

## Reversal

Stop the hosted service. Nothing else changes; the private server (`http` mode) is untouched apart from `build_server(public=False)` being the default.
