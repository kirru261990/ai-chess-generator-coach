# 0008. The practice board inside Claude and ChatGPT (MCP Apps)

Date: 2026-10-17 · Status: accepted · Builds on ADR 0007 (practice over MCP)

## Context
The text board from ADR 0007 is hard to read in chat (symbol glyphs fall back to other fonts and drift out of line; White comes out
as tiny outlines). The owner wants the same interactive board as the web app inside the chat.

## Decision
1. **Use MCP Apps** (`io.modelcontextprotocol/ui`): a tool carries `_meta.ui.resourceUri` pointing at a `ui://` resource served as
   `text/html;profile=mcp-app`. The chat renders that HTML in a sandboxed frame and passes the tool result to it; the page calls
   the practice tools back through the chat. Both Claude and ChatGPT support it. `mcp` 2.3 already ships the server side
   (`mcp.server.apps`), so no Python dependency is added.
2. **The board is the web app's Practice page**, not a second copy. `Practice.tsx` takes a `PracticeBackend`: the web app passes the
   REST one, the chat page passes `toolBackend`, which turns each step into a tool call. The rules, the engine check and the scoring
   stay on the server, and the page decides nothing (AGENTS rule 1).
3. **One data shape.** Every board-showing tool still returns its text (all a client without app support gets) and now also
   `structuredContent = {view, summary}`, the same `learner.practice.get_session` view the web API serves. A refused step is text only.
4. **One HTML file, no network.** `pnpm build:mcp` (Vite + `vite-plugin-singlefile`) builds `web/board.html` into
   `backend/app/mcp/ui/board.html`, which is committed so the server runs without Node. It loads nothing from outside, so the strict
   sandbox policy (no outside addresses) needs no exceptions. Rebuild it after changing `Practice.tsx`, `MoveArrows.tsx`,
   `practiceState.ts`, `practiceBackend.ts` or `src/mcp-board/`. If the file is missing the server serves a short notice instead and
   the text board still works.
5. **The text board changes to letters** (CAPITALS White, lowercase Black) in a fixed-width block; it stays as the fallback.
6. **New web dev dependencies** (bundled into the file, all permissive): `@modelcontextprotocol/ext-apps` (MIT),
   `@modelcontextprotocol/client` and `core` (Apache-2.0, peers of ext-apps), `zod` (MIT), `vite-plugin-singlefile` (MIT). Rows are in
   `THIRD_PARTY.md`.

## Not changed
Still Practice only: no tool starts or takes a starting or delayed test (ADR 0007). Practice is always assisted. Play and assisted
games against Stockfish in chat are a separate step (its own ADR), because they add tools and must show no help in Play (rule 4).

## Reverse
Remove `extensions=[apps]` and the `ui` bindings in `app/mcp/server.py`; the tools return plain text as before.

## Known unknowns
Claude and ChatGPT differ in small ways (the tool metadata key name differs between the docs: nested `ui.resourceUri` here, and
`openai/outputTemplate` is also set for ChatGPT). Verified in a mock host built with the SDK's own host class (`AppBridge`), a
sandboxed frame and the real server; real clients are checked by the owner and recorded in `docs/mcp-setup.md`.
