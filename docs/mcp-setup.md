# Practice in Claude chat and ChatGPT: setup

Practice mode (Replay My Mistakes) as chat tools. Design: `docs/mcp-practice-plan.md`; decisions: ADR 0007. **Practice only**: the
starting and delayed tests stay in the web app, and no tool can reach them.

You need a Mac where a tunnel program is allowed (not a locked-down work laptop), with this repo, `data/coach.sqlite3`, `.env`
(with `STOCKFISH_PATH`) and the pinned Stockfish. The Mac must be on, with the server and the tunnel running, whenever the chat
uses it. Your games never leave the Mac.

## Steps

1. **Get the code.** `git fetch && git checkout feat/mcp-practice` (or `main` once merged). Use `git worktree add` if the web app is
   being served from this folder.
2. **Choose the login password** (at least 12 characters; it is stored hashed, locally, and never printed):
   ```bash
   cd backend && uv run python -m app.mcp.setup
   ```
3. **Start the tunnel** (Cloudflare quick tunnel: no account, but a **new address every run**):
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8765
   ```
   Copy the `https://….trycloudflare.com` address. `cloudflared` is Cloudflare's program: Homebrew has it
   (`brew install cloudflared`), or use the release from https://github.com/cloudflare/cloudflared/releases. For a stable address
   use a named Cloudflare tunnel (free account and a domain) or ngrok's free static domain.
4. **Put the address in `.env`** (git-ignored; no trailing slash or path): `MCP_PUBLIC_URL=https://….trycloudflare.com`
   (`MCP_PORT` defaults to 8765).
5. **Start the server** and leave it running:
   ```bash
   cd backend && uv run python -m app.mcp.server http
   ```
   It refuses to start without an https `MCP_PUBLIC_URL` and a password.
6. **Claude:** Customize → Connectors → add a custom connector, address `<MCP_PUBLIC_URL>/mcp`. Sign in on the page that opens,
   with your password. Then say: "Practise my pieces left in danger."
7. **ChatGPT** (Plus: expect problems, see below): Settings → Connectors → Advanced → Developer mode → New connector, same
   address, authentication OAuth, sign in.

A quick tunnel gets a new address each run: change `MCP_PUBLIC_URL`, restart the server and add the connector again.

## Using it from Claude Desktop or Claude Code on the same Mac (no tunnel, no login)

```bash
cd backend && uv run python -m app.mcp.server stdio
```
Add it to the client as a local MCP server with that command (working directory `backend/`). It never opens a network port.

## The interactive board (ADR 0008)

In Claude and ChatGPT the practice tools also draw the web app's board inside the chat (tap a piece, click a move, the yellow and green
arrows, the star, and the replay with the arrow keys). A client that cannot show it still gets the text board (letters: CAPITALS White,
lowercase Black). The board is one HTML file, `backend/app/mcp/ui/board.html`, built from `web/` with `pnpm build:mcp` and committed;
rebuild it after changing the Practice page. Restart the server, and in Claude remove and add the connector again (or start a new
chat) so it re-reads the tool list.

## Games against Stockfish in chat (ADR 0009)

Seven more tools play a game on the same board: `game_new` (colour, level 1 to 10, mode `play` or `practice`), `game_move` (`Nf3`,
`exd5`, `O-O` or `g1f3`; Stockfish replies in the same call), `game_show`, `game_resign`, and, **Practice games only**, `game_undo`,
`game_hint` (steps 1 to 5) and `game_threats` (arrows on or off). Say: "Play a game against level 3, I am White", or "start an
assisted game".

- **Play shows no help, anywhere.** The board, a one-line status and Resign only. No verdict, evaluation, badge, hint, undo or threat
  arrows: not in the widget, not in the tool text, not in the data. There is no tool to switch a game's mode.
- **Practice (assisted)** shows what the web app's Practice shows, except the evaluation bar and "Why?" (not in chat yet): the
  verdict and badge on your last move, red and green marks, threat arrows (toggle), the hint ladder and Undo.
- The board page uses two extra tools meant for it alone, `game_apply_move` and `game_engine_move` (marked app-only), so your move shows at once and Stockfish replies about a second later. If your chat model lists them, it is told never to call them.
- **Limits:** chat games live in memory in the MCP server process. They are **not saved**, are **not the web app's games** (the two
  servers do not share them), vanish when the server restarts, and at most 20 are kept. They enter no progress number or review.
  Real unassisted evidence stays in the web app.
- The chat model sees the board and may comment on a Play game anyway (the server's instructions tell it to only relay): guidance, not
  enforcement. Treat chat Play as casual.
- The board is still `backend/app/mcp/ui/board.html` (rebuild with `pnpm build:mcp` after changing `GameBoard.tsx`, `gameBackend.ts`
  or `mcp-board/main.tsx`). Claude caches the tool list: **remove and add the connector again** after updating.

## What it does

`practice_status`, `practice_start` (`pieces_in_danger` or `free_pieces`), `practice_show`, `practice_answer` (a square or
`none`), `practice_move` (`Nf3`, `O-O`, `g1f3`), `practice_hint`, `practice_retry`, `practice_next`, `practice_summary`,
`progress`. Every move is checked by the engine; the wording is the same as on the web page. Practice is always assisted.

## Security

- Sign-in is OAuth with one password. Five wrong passwords lock it for 15 minutes. Tokens are random and stored only as hashes in
  `data/mcp_auth.sqlite3` (git-ignored, separate from the learning store). Access tokens last 1 hour, refresh tokens 30 days.
- Only Claude, ChatGPT and localhost redirect addresses can register. Any other `Host` header is refused.
- **Anyone who can sign in can read your practice data and make attempts.** Use a password you use nowhere else. To sign
  everything out: stop the server, delete `data/mcp_auth.sqlite3`, run the setup again.
- The password, the auth database and the tunnel address never go into a commit (the repo is public).
- The chat model can see the board and may try to analyse it. The server's instructions tell it to only relay the tool; that is
  guidance, not enforcement. Practice is assisted, so this does not affect any score.

## Verified

Run end to end on 2026-10-16 on a scratch copy of the store with the real engine, over HTTP and the full login, from the `mcp`
Python client (a five-position session, a refused step, no token → 401, foreign host → 421). **Not yet tried with the real
Claude or ChatGPT clients** (plan step 7). Record here what each client does: whether Claude's `/revoke` works for its client
type (the library asks for a client secret), and whether ChatGPT Plus allows the tools that change data (`practice_start`,
`practice_answer`, `practice_move`, `practice_hint`, `practice_retry`, `practice_next`). If it refuses them, ChatGPT can still
use `practice_status`, `practice_summary` and `progress` (the only read-only tools: `practice_show` saves the first attempt of a new session, so it counts as a write); practice itself stays on Claude and the web app.

### Tried in the real Claude (2026-10-17, claude.ai in Chrome, Pro plan)
- **Added as a custom connector** (form: sign in now, register automatically, no headers). The sign-in page asked for the password and Claude listed all ten tools, sorted as read-only (3) and write (7). The server log showed the whole OAuth flow (register, authorize, login, token).
- **The interactive board works** (ADR 0008): after `practice_show` Claude read `ui://chess-coach/board.html`, drew the board, and its clicks came back as `practice_answer`, `practice_move`, `practice_retry` and `practice_next` calls. The owner played several positions with it ("worked fine").
- **Claude caches the tool list** from when the connector was added. After the tools change (for example the board binding) remove and add the connector again; a new chat alone is not enough.
- **The model adds its own commentary** to relayed text (it explained why a piece hung) although the server's instructions say to only relay: guidance, not enforcement. The board hides this because the board itself carries the feedback.
- **Not yet checked:** ChatGPT, Claude Desktop with the remote connector, and `/revoke`.

