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

## Keeping it awake (and letting it sleep at night)

Render's free instance sleeps after about 15 minutes without a visit; the next request takes 50 seconds or more. `.github/workflows/keep-awake.yml` visits `/healthz` every 10 minutes from **05:00 to 23:20 IST** (the schedule is in UTC; runs may start a few minutes late). After 23:20 nothing visits, so the instance sleeps by about 23:35 IST and wakes on the first request after 05:00 (or on a night visitor's first move, with the usual wait). That is about 18 awake hours a day, inside Render's free monthly hours (check their current terms).

- GitHub stops scheduled runs after 60 days with no repo activity: re-enable under Actions, or press "Run workflow".
- **UptimeRobot** (free account, monitor on `/healthz`, every 5 minutes) pings around the clock and cannot be limited to hours on the free plan (maintenance windows are paid). To get the night sleep, keep that monitor **paused**; resume it only if you want the server awake all day and night.

## Sharing it with friends

Anyone can add it: Customize → Connectors → add a custom connector, address `https://chess-coach-public.onrender.com/mcp`, no sign-in; then a new chat: "new chess game, level 2, I am black". Notes to give them:
- Needs a Claude plan that allows custom connectors (not checked for free accounts).
- The board shows on **claude.ai in a browser** and in **ChatGPT**. The **Claude Desktop app does not draw it** (a known Claude bug, ext-apps issue 671): they see text and moves only.
- In ChatGPT: Plugins → Add → Add custom MCP server, no authentication (steps above).
- Several players at once share one small CPU and one Stockfish, so replies slow down, Practice verdicts most.
- Their chat costs them nothing extra and costs you nothing. Privacy: `/privacy`.

## ChatGPT

Tried on a Plus plan, 2026-10-25: ChatGPT → Plugins → **Add** → **Add custom MCP server**; name "Chess Coach", server URL `https://chess-coach-public.onrender.com/mcp`, authentication **No authentication**, tick the "I understand" box, create, then click through the "Connect" consent. In a new chat type `@`, choose Chess Coach, then ask: "new chess game, level 2, I am black, practice mode".
- The interactive board draws, moves and Practice verdicts work, Stockfish replies, the larger side panel works. No per-move approval prompts appeared (default permission "Allow low-risk tools"); a stricter setting may ask each time.
- ChatGPT also prints the game id, move list and FEN as text beside the board.
- Not checked: other plans, ChatGPT's directory submission (the owner's to make; same privacy page).

## Deploying a change

Render does **not** deploy by itself (the service was made from the public repo address, so GitHub cannot notify it). After merging to `main`: Render dashboard → the service → **Manual Deploy → Deploy latest commit** (about a minute). Check the live board page is the new one by comparing the sha256 of `backend/app/mcp/ui/board.html` with the page the server returns for `resources/read ui://chess-coach/board.html`. In Claude, remove and add the connector again after a tool change.

## Board page size (2026-10-25)

With the SDK's client and schema libraries the board page was 562 KB and claude.ai did not draw it (the server log showed the page requested about ten times in a row, then no call back). `web/src/mcp-board/miniApp.ts` replaced the SDK's `App` with the few messages the board uses (recorded from the real library): the page is 330 KB and draws. Whether size was the cause is a guess that fits the result. If a host stops drawing it again, check the Render log for `resources/read` followed by `game_show`.

## Putting it in Claude's public directory (needs you)

Adding it by address works for anyone who pastes the link. A listing in Anthropic's connector directory is a separate submission I cannot make for you. You have the stable address and a privacy page (`/privacy`); it also needs a support contact (the GitHub issues page is used on the privacy page, since the repo is public and your email must not go in it) and Anthropic's review. Check the current submission requirements on Anthropic's site: a service that sleeps for 50 seconds may count against it, and then a paid always-on instance would be the fix.

## Limits

500 games at once, 2 hours idle, 600 requests a minute for the whole service, then HTTP 429. One shared Stockfish process, so heavy use makes replies slower. The repo is AGPL-3.0: a hosted copy must offer its source (the public GitHub repo does).
