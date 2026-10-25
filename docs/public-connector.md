# The open chess connector: how to publish it

Games against Stockfish (Play, or Practice with hints, undo and threat arrows) for anyone, from Claude chat. No login, no stored data, no model calls. Decision: ADR 0010. Your private practice connector (`docs/mcp-setup.md`) is a different server and is not affected.

**Live (2026-10-25):** `https://chess-coach-public.onrender.com/mcp` (Render free plan). Privacy page: `https://chess-coach-public.onrender.com/privacy` (source: `backend/app/mcp/public_pages.py`; keep it true to ADR 0010 when limits change).

## What users get

`game_new` (colour, level 1 to 10, mode `play` or `practice`), `game_move`, `game_show`, `game_resign`, and in Practice games `game_undo`, `game_hint`, `game_threats`, with the interactive board. Say: "Play chess against level 3, I am White."

## Try it on your Mac first

```bash
cd backend && MCP_PUBLIC_URL=https://example.org MCP_PORT=8765 uv run python -m app.mcp.server public
```
That only proves it starts; the address must be https and the real one for the host checks to pass from outside.

## Host it for free on Render

The `Dockerfile` at the repo root installs Stockfish and starts the open server. Hugging Face Docker Spaces turned out to be paid (2026-10-25); Render's free web service works.

1. render.com, sign in, **New → Web Service → Public Git Repository**, paste the repo address, Connect (no GitHub permission needed for a public repo).
2. Name it (the name becomes `https://<name>.onrender.com`), language Docker, branch `main`, instance type **Free**.
3. Environment variable `MCP_PUBLIC_URL` = `https://<name>.onrender.com` (no trailing slash). No other variable, and no secret: do not give it `ANTHROPIC_API_KEY`. Render sets `PORT` itself.
4. Deploy. When the log says it is live, `https://<name>.onrender.com/healthz` says `ok`.
5. In Claude: Customize → Connectors → add a custom connector, `https://<name>.onrender.com/mcp`, no sign-in.

If Render gives the service a different address than the one you typed (the name was taken), change `MCP_PUBLIC_URL` to match and redeploy, or every request is refused (HTTP 421).

Free instances sleep after about 15 minutes idle; the next request takes 50 seconds or more. They have 0.1 CPU and 512 MB, so heavy use is slow. Render's free terms can change.

## Putting it in Claude's public directory (needs you)

Adding it by address works for anyone who pastes the link. A listing in Anthropic's connector directory is a separate submission I cannot make for you. You have the stable address and a privacy page (`/privacy`); it also needs a support contact (the GitHub issues page is used on the privacy page, since the repo is public and your email must not go in it) and Anthropic's review. Check the current submission requirements on Anthropic's site: a service that sleeps for 50 seconds may count against it, and then a paid always-on instance would be the fix.

## Limits

500 games at once, 2 hours idle, 600 requests a minute for the whole service, then HTTP 429. One shared Stockfish process, so heavy use makes replies slower. The repo is AGPL-3.0: a hosted copy must offer its source (the public GitHub repo does).
