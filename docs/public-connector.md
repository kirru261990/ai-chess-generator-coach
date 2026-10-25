# The open chess connector: how to publish it

Games against Stockfish (Play, or Practice with hints, undo and threat arrows) for anyone, from Claude chat. No login, no stored data, no model calls. Decision: ADR 0010. Your private practice connector (`docs/mcp-setup.md`) is a different server and is not affected.

## What users get

`game_new` (colour, level 1 to 10, mode `play` or `practice`), `game_move`, `game_show`, `game_resign`, and in Practice games `game_undo`, `game_hint`, `game_threats`, with the interactive board. Say: "Play chess against level 3, I am White."

## Run it on your Mac first (free, 2 minutes)

```bash
cd backend && MCP_PUBLIC_URL=https://example.org MCP_PORT=8765 uv run python -m app.mcp.server public
```
That only proves it starts. For real use it needs a stable https address (below).

## Host it for free (no Mac needed)

The `Dockerfile` at the repo root installs Stockfish and starts the open server. Any free Docker host works; **Hugging Face Spaces (Docker, free CPU)** is the simplest: it gives a stable `https://<user>-<space>.hf.space` address. Free tiers change and may sleep when idle, so check the host's current terms before relying on it.

1. Create a Space, type Docker, public.
2. Push this repo to it (or link the GitHub repo). Set the Space variable `MCP_PUBLIC_URL` to its https address, no trailing slash. The container listens on `PORT` (7860).
3. Check `https://<address>/healthz` says `ok`.
4. In Claude: Customize → Connectors → add a custom connector, address `https://<address>/mcp`, no sign-in. Play a game.

Keep no secrets on the host: it needs none. Do not give it `ANTHROPIC_API_KEY`.

## Putting it in Claude's public directory (needs you)

Adding it by address works for anyone who pastes the link. A listing in Anthropic's connector directory is a separate submission I cannot make for you: it needs the stable address above, a privacy policy page (ADR 0010 says what is true: no accounts, no storage, games kept in memory up to 2 hours, logs hold tool names only), a support contact and Anthropic's review. Check the current submission requirements on Anthropic's site before applying.

## Limits

500 games at once, 2 hours idle, 600 requests a minute for the whole service, then HTTP 429. One shared Stockfish process, so heavy use makes replies slower. The repo is AGPL-3.0: a hosted copy must offer its source (the public GitHub repo does).
