# Practice mode as a chat tool (Claude chat and ChatGPT): design and plan

**Status:** steps 1 to 6 built on `feat/mcp-practice` (2026-10-16); **step 7 (connect from Claude and ChatGPT) is not done**: it needs a
Mac where a tunnel is allowed. See `docs/mcp-setup.md` and ADR 0007. Originally written so a new session could read this file, `HANDOFF.md`,
`docs/prd-v2.md` §11 and ADR 0006, and start building at step 1. Task: `TASKS.md` P5 / T45.

## 1. What and why

Let the owner do **Replay My Mistakes** from a chat window: ask "practise my hanging pieces", see a position, answer by typing a
square and a move, get the engine-checked feedback, ask for hints, finish a session. It is the same practice as the web app, on
a second surface (spec C4: web app + MCP, ChatGPT and Claude as secondary clients; PRD §11: both call the same service layer and
neither has its own scoring logic).

**In scope (practice only):** status, start or resume a session, show the position, answer the question, make the move, hint,
retry, next, summary, and a read-only progress summary.

**Out of scope, by decision:** the starting and delayed **tests** stay in the web app. A chat assistant can talk about a position
and help, so a test taken through it would not be unassisted (AGENTS rule 4). Starting a baseline, taking a test and the web
board are not exposed. Play-vs-Stockfish and the review tabs are also out of scope.

## 2. What the two clients require (checked 2026-10-16)

| | Claude chat (claude.ai custom connector) | ChatGPT (developer mode connector) |
|---|---|---|
| Server | **Remote**, publicly reachable over HTTPS. Streamable HTTP (SSE is being phased out) | **Remote**, public. Streamable HTTP or SSE. A local stdio server does not work |
| Login | Authless or **OAuth** (DCR supported; or a client id and secret entered by hand) | No authentication, **OAuth**, or "mixed" |
| Plans | Pro, Max, Team, Enterprise | Developer mode exists, but **whether Plus may call tools that change data is unclear** (see §9) |
| Callback | `https://claude.ai/api/mcp/auth_callback` (may move to a claude.com domain) | ChatGPT's own redirect URL, shown in the connector dialog |

Neither accepts a simple password header, so protecting the server means **OAuth** (or no protection). Sources: Anthropic,
[building custom connectors via remote MCP servers](https://support.claude.com/en/articles/11503834); OpenAI,
[developer mode and full MCP connectors](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta.eot)
and the [developer mode guide](https://developers.openai.com/api/docs/guides/developer-mode). Re-check both before relying on a
detail: they are betas and change.

## 3. Decisions already made with the owner

1. **Reachable from the owner's Mac, with a login** (not a secret link, not local-only, not a cloud server). The data stays on
   the Mac. The Mac has to be on and the tunnel running while the chat uses it.
2. **ChatGPT Plus** is the owner's plan: try it, and expect that tools which change data may be refused there. Claude is the
   reliable first target.
3. Practice only (above). Plain-text boards first (below). No new dependency: `mcp>=2.3.0` and `uvicorn` are already direct
   dependencies, so `THIRD_PARTY.md` needs no row.

## 4. Architecture

```
Claude chat / ChatGPT
        │  HTTPS (Streamable HTTP, OAuth bearer token)
        ▼
 tunnel (Cloudflare or ngrok)  ── public URL = MCP_PUBLIC_URL
        │  http, same machine only
        ▼
 uvicorn on 127.0.0.1:8765  ──  MCPServer("chess-coach")
        │                         ├─ OAuth: /authorize → /login (password page), /token, /register, /revoke, metadata
        │                         └─ tools: practice_* , progress          (app/mcp/practice_tools.py: words only)
        ▼
 the service layer the web app uses:  learner/practice.py, learner/progress.py, learner/assessment.py
        ▼
 data/coach.sqlite3 (the learning store)      data/mcp_auth.sqlite3 (logins and tokens, separate file)
        └─ Stockfish via open_evidence for the move check
```

Rules kept: the backend owns chess state (rule 1); no tactical claim without a check (rule 2: feedback is the template built
from the evidence record); practice is always assisted (rule 4); held-out positions never reach practice (SQLite refuses it).

## 5. The tools

All take plain arguments and return **one markdown message** (what the chat shows). A refused step comes back as a sentence
("I could not do that: …"), never a traceback.

| Tool | Arguments | Does | Annotations |
|---|---|---|---|
| `practice_status` | none | per mistake type: locked or ready, positions left, open session, the delayed test and when it opens | read-only |
| `practice_start` | `mistake_type`: `pieces_in_danger` or `free_pieces` | start a session or resume the open one; returns position 1 | changes data |
| `practice_show` | `session_id` | the current position and what to do next (safe to call again; the first view of a new session saves its first attempt) | changes data |
| `practice_answer` | `session_id`, `square` (`g5`, or `none` / "no immediate threat") | step 1 (the question); accepts only pieces of the asked side | changes data |
| `practice_move` | `session_id`, `move` (SAN `Bf4`, `Nxe5`, `O-O`, or UCI `g5f4`) | step 2; the engine checks it (about 2 s); feedback follows | changes data |
| `practice_hint` | `session_id` | the next of three hints; marks the try assisted | changes data |
| `practice_retry` | `session_id` | the same position again, a new try | changes data |
| `practice_next` | `session_id` | next position; after the last, the session finishes and the delayed test is scheduled | changes data |
| `practice_summary` | `session_id` | the finished session's summary and the delayed-test line | read-only |
| `progress` | none | tests and assisted practice kept apart (the same numbers as My progress) | read-only |

The tool layer finds the current position's `ord` itself (the web app passes it to stop a double click; in chat the stage checks
do that: a repeated answer gets "this position is at the move step"). Hints and answers use `learner/practice.py` unchanged.

## 6. What the chat shows

A code block in a fixed-width font works in both clients without any picture support:

```
Pieces left in danger: position 2 of 5 (try 1) · session 7 · assisted practice
You play white and it is your move.

    a  b  c  d  e  f  g  h
8   ♜  ·  ♝  ·  ♚  ♝  ♞  ♜  8
…
FEN: …

Step 1, a question first (not a move yet). Which of YOUR pieces can the other side win?
Reply with its square (for example g5), or say "no immediate threat".
Pieces you can name: Kg1, Qd1, Ra1, Rh1, pawns a2 b2 c2 …
Use practice_answer with the square, or "none".
Hints are optional (3 left): practice_hint.
```

- Drawn from the player's side; squares to point out (a hint, the piece at risk in the feedback) are in `[brackets]`.
- The FEN and a piece list are included for plain-text and screen-reader clients.
- Wording matches the web page (plain words; the owner finds notation hard), including the "saves your piece, but a stronger move
  existed" sentences, the "allows checkmate" case, and "one line the engine found (not the only one)".
- **Later, not v1:** a board picture (a PNG tool result; needs a renderer and a licence check) and an interactive board where a
  client supports MCP interactive UI. Do not add a dependency without a `THIRD_PARTY.md` row (a test fails otherwise, and
  copyleft packages are refused).

## 7. Keeping it honest in a chat

- **The same leak rules, for free:** the tool layer only renders what `get_session` returns, so before the first answer a message
  holds the board, the side to move and the pieces that can be named, and nothing else. A leak test over the tool outputs is
  required (as in `tests/test_practice.py` and `tests/test_coach_api.py`).
- **The chat model can still see the board and may try to analyse it.** Practice is assisted, so this is not a scoring risk, but
  it would blur "what the engine verified" and "what the model says". Put this in the server `instructions` (sent to the client):
  *you only relay this tool; never analyse the position, suggest a move or say whether an answer is right before the tool does;
  never call practice_hint unless the player asks; show the tool's text as is.* This is guidance, not enforcement: say so in the docs.
- Tool descriptions must say plainly which tools change data (annotations: `readOnlyHint` true only for status, summary,
  progress (show is not: the first view of a new session writes its first attempt, found in the PR 77 review); `destructiveHint` false everywhere; no tool deletes anything).
- Errors never expose paths, SQL or tracebacks.

## 8. The login (OAuth for one person)

The `mcp` library already serves the OAuth endpoints, token checks and metadata when given an `OAuthAuthorizationServerProvider`
(`mcp.server.auth.provider`) and `AuthSettings`. We write the provider and one login page.

**Provider (`app/mcp/auth.py`), SQLite file `data/mcp_auth.sqlite3` (git-ignored, separate from the learning store):**
- `register_client` (dynamic client registration, enabled): accept only redirect URIs whose host is `claude.ai`, `claude.com`,
  `chatgpt.com`, `chat.openai.com`, `platform.openai.com`, or `localhost` / `127.0.0.1` (for Claude Code, the MCP Inspector and
  tests). Anything else is refused (`invalid_redirect_uri`): otherwise anyone could register a look-alike client.
- `authorize`: store the pending request (client, PKCE challenge, redirect, state) under a random id (10 minutes); return the URL
  `{MCP_PUBLIC_URL}/login?request=<id>`.
- **Login page** (`/login`, a custom route): GET shows a form naming the client and its redirect host and what it grants
  ("practice only; no tests"); POST checks the password, creates a single-use authorization code (at least 160 bits, 5-minute
  expiry), and redirects to the client's `redirect_uri` with `code` and `state` (`construct_redirect_uri`). Headers:
  `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, a CSP that allows only the page itself.
- **The password:** set once with `python -m app.mcp.setup` (hidden prompt, never in chat or a file you commit). Stored as a
  scrypt hash (`hashlib.scrypt`, random salt) in the auth database. Constant-time compare. **Lock-out:** 5 wrong passwords lock the
  login for 15 minutes (one owner, so the counter is global and persisted).
- Codes and tokens: `secrets.token_urlsafe(32)`; **only SHA-256 hashes are stored**. Access token 1 hour; refresh token 30 days
  with rotation (a used refresh token is replaced); `revoke_token` implemented; a code is deleted when exchanged.
- One scope, `practice`. `load_access_token` checks expiry and returns the token's client and scope; nothing else is trusted.
- `AuthSettings(issuer_url=MCP_PUBLIC_URL, resource_server_url=MCP_PUBLIC_URL + "/mcp", validate_token_resource=True,
  client_registration_options=enabled, revocation_options=enabled, required_scopes=["practice"])`.
- **DNS-rebinding and host checks:** `TransportSecuritySettings(allowed_hosts=[<public host>, "127.0.0.1:8765", "localhost:8765"],
  allowed_origins=[<public origin>, https://claude.ai, https://chatgpt.com, …])`.
- Bind `127.0.0.1` only; HTTPS comes from the tunnel. Refuse to start in HTTP mode without `MCP_PUBLIC_URL` and a password set.

**Environment (`.env`, git-ignored; add the names, not values, to `.env.example`):** `MCP_PUBLIC_URL`, `MCP_PORT` (default 8765).
The password is not an environment variable.

## 9. The tunnel, and the owner's accounts

The owner has to create any account or sign in to a tunnel service: an agent cannot, and should not download a tunnel binary
without asking (state the file, source and size first).

| Option | Account | URL | Note |
|---|---|---|---|
| Cloudflare quick tunnel: `cloudflared tunnel --url http://127.0.0.1:8765` | none | **new random address every run** | fine to try; the connector must be re-added each time, and `MCP_PUBLIC_URL` changed |
| Cloudflare named tunnel | free account and a domain | stable | best for daily use |
| ngrok with its free static domain | free account | stable | simple; one static domain per account |

A stable URL matters: the connector, the OAuth issuer and the host allowlist all contain it.

## 10. Build order (each step has tests; one PR per step or one PR for the lot, owner's choice)

1. **`app/mcp/board_text.py`:** the board from either side with `[marked]` squares, a piece list in words. Tests: both sides,
   marks, a position from the owner's real store.
2. **`app/mcp/practice_tools.py`:** the ten functions above, each taking a connection (and an analyser opener) so tests can script
   them; `render_session` for every stage (recognition, move, feedback, finished). Move parsing: UCI first, then SAN (try
   `Bf4`, `bf4`, capitalised, ambiguous moves refused with "add the square it starts from", `O-O`, `0-0`). Tests: a full session
   through the tool functions with the scripted engine used in `tests/test_practice.py`; every refused step is a sentence; the
   **leak test** over every message before the first answer (no best move, eval, line, target squares, verdict, later boards, held-out boards).
3. **`app/mcp/server.py`:** build the `MCPServer`, register the tools with annotations and the `instructions`; entry points
   `python -m app.mcp.server stdio` (Claude Desktop and Claude Code on the Mac, no login needed locally) and `... http`
   (uvicorn). Keep the existing `get_game` tool or retire it with a note. Test: list the tools in-process and call each through
   `MCPServer.call_tool`.
4. **`app/mcp/auth.py` and `app/mcp/setup.py`:** the provider, the login page, the password setup, lock-out, the redirect
   allowlist. Tests (Starlette `TestClient` on `streamable_http_app()`): no token → 401 with the protected-resource metadata; dynamic
   registration accepted for the allowed hosts and refused for another; the full flow (register, authorize, wrong password refused,
   lock-out after 5, right password, code exchange with PKCE, call a tool with the token); a code works once; an expired token is
   refused; a refresh token rotates; revoke works; a token for another resource is refused; headers present; a wrong `Host` is refused.
5. **Run it for real on a scratch copy of the store** (`DATA_DIR`): start it, drive it with the `mcp` Python client through the
   OAuth flow, and play a session over HTTP.
6. **Docs:** `docs/mcp-setup.md` (the owner's steps below), ADR 0007 (these decisions), `HANDOFF.md`, `TASKS.md`, `AGENTS.md`
   commands (`python -m app.mcp.setup`, `python -m app.mcp.server http|stdio`), `.env.example` names, `README.md` works table.
7. **Connect it (owner and agent together):** run the tunnel, set `MCP_PUBLIC_URL`, run the server, add the connector in Claude
   (Customize → Connectors → add the URL), sign in at the login page, play a position. Then ChatGPT (Settings → Connectors →
   Advanced → Developer mode → New connector, OAuth). Record what ChatGPT Plus allows in `docs/mcp-setup.md`.

**Exit gate:** a full five-position session works from Claude chat over the tunnel with the login; the leak test passes; a wrong
password, an old token and a foreign `Host` are all refused; nothing outside practice is reachable (calling any test tool fails
because none exists).

## 11. Risks and open items

- **ChatGPT Plus may refuse tools that change data.** If it does: ChatGPT can still use the read-only tools (`practice_status`,
  `practice_summary`, `progress`; `practice_show` is a write on a new session, see the PR 77 review), and practice itself stays on Claude chat and the web app. Do not weaken the
  design to fit (for example a move tool marked read-only that still records attempts: that would hide a write).
- **The Mac must be on and the tunnel running.** A cloud deployment would remove that but puts the games in the cloud (decision 1).
- **Anyone who can sign in can read your practice data.** Hence the password page, lock-out, hashed tokens and the redirect allowlist.
  The repo is public: the password, the auth database and the URL never go into a commit.
- **The chat model may analyse the board itself** (section 7). Mitigated by instructions, not enforced.
- **Engine time:** a move takes about 2 seconds (an uncached position search); fine for chat. Each call starts its own pinned
  Stockfish (as the web API does); do not hold one open across calls.
- **Two requests at once:** the service layer is already safe (one write transaction with the check inside, ADR 0006
  decision 35); the tool layer must not add its own read-then-write.
- **Tool names and descriptions are read by a model:** keep them short and literal; test a real chat for double calls
  (answer then answer again) and make sure the refusal sentence steers it back.
- **Spend:** none. No model call is made by this server (feedback is the template); P3b (LLM wording) is separate.

## 12. The owner's setup steps (to go into `docs/mcp-setup.md` when built)

1. `cd backend && uv run python -m app.mcp.setup` (choose the login password; it is stored hashed, locally).
2. Start the tunnel; copy its HTTPS address into `.env` as `MCP_PUBLIC_URL`.
3. `uv run python -m app.mcp.server http` (leave it running).
4. Claude: add the connector with `<MCP_PUBLIC_URL>/mcp`, sign in with the password when asked.
5. ChatGPT: enable developer mode, add the same URL as a connector with OAuth, sign in.
6. In a chat: "Practise my pieces left in danger."
