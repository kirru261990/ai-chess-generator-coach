"""The open server's one web page: the privacy policy, served at /privacy. Keep it true to ADR 0010 and the code
(`game_tools.configure`, `PublicGuard`, `run_public`): change the page when any of those change."""

PRIVACY_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chess Coach connector: privacy</title>
<style>body{font:16px/1.55 system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h1{font-size:1.5rem}h2{font-size:1.1rem;margin-top:1.6rem}code{background:#f1f1f1;padding:0 .25em;border-radius:3px}</style></head>
<body>
<h1>Chess Coach connector: privacy</h1>
<p>Last updated 25 October 2026. This covers the open chess connector at this address, which plays games against Stockfish for
anyone who adds it to Claude.</p>

<h2>Short version</h2>
<p>No accounts, no sign-in, no database, no cookies, no analytics, no advertising. Nothing you do here is written to disk or
linked to you.</p>

<h2>What the connector receives</h2>
<p>Only what Claude sends when you play: the colour, level and mode you chose, your moves, and the id of your game. It does not
see your name, email, conversation or anything else about you.</p>

<h2>What it keeps, and for how long</h2>
<ul>
<li>Each game (its moves and board position) is held in the server's memory only. It is forgotten after 2 hours without a move,
when the server restarts, or sooner if more than 500 games are open at once.</li>
<li>Nothing is saved to a file or database, and games are not tied to a person.</li>
<li>The connector's own log records only the kind of request and the tool name, for example <code>tools/call game_move</code>.
It does not record game contents, addresses or any identifier, and the web server's access log is switched off.</li>
</ul>

<h2>What it does not do</h2>
<ul>
<li>It does not call any AI model and does not send your data to any other service.</li>
<li>It does not sell or share data, because it does not keep any.</li>
</ul>

<h2>Other parties</h2>
<ul>
<li><strong>Claude and Anthropic</strong> handle your conversation under their own terms and privacy policy. This connector
cannot see your conversation, and Claude shows the board and moves it receives from this connector to you.</li>
<li><strong>The hosting provider</strong> (Render) runs this service and, like any host, may keep its own technical records of
network requests under its own policy. We do not control or receive those records.</li>
</ul>

<h2>Children</h2>
<p>The connector asks for no personal information from anyone. Claude's own age rules apply to using Claude.</p>

<h2>Questions</h2>
<p>The code is open source (AGPL-3.0): <a href="https://github.com/kirru261990/ai-chess-generator-coach">github.com/kirru261990/ai-chess-generator-coach</a>.
Questions or concerns: open an issue there. If this policy changes, this page and its date change with it.</p>
</body></html>
"""
