# 0023. Practising from another computer: one address, a password, a tunnel from the owner's Mac

Status: accepted (owner, 2026-11-12: "I want to practice in office as well, so via the server only I can do it"; chose "Home Mac + tunnel + password"). The grilling step was skipped; decisions below are mine and open to change.

## Context

The API and the web app run on the owner's Mac at `localhost`. The API has no login and holds the owner's synced games, their progress and a model budget, so a bare tunnel to it would publish all of that. The owner wants the Practice and Openings tabs from an office computer, possibly a locked-down one, so the office side should need only a browser.

## Decisions

1. **The Mac serves everything; the office needs only a browser.** The API serves the built web app (`web/dist`) at `/`, after all API routes, so one address carries both. The web app is built with `VITE_API_URL` empty, which makes its calls relative. Without a build nothing changes: Vite serves the page in development as before.
2. **A request from outside needs a password; local use stays open.** A request is local only if it names a loopback host and carries no proxy header (`cf-connecting-ip`, `x-forwarded-for`, `forwarded`, `cf-ray`, `x-forwarded-host`). Everything else needs HTTP Basic with the access password (any user name). Failing closed: with no password set, remote requests get 503. The password is stored as a scrypt hash in `data/access.json` (git-ignored, mode 600), compared in constant time; five wrong tries lock remote access for 15 minutes (one owner, so the counter is global, as in the MCP login, ADR 0007). The first visit without credentials is only the browser asking for the login box and does not count as a try.
3. **Cloudflare quick tunnel, started by `scripts/office.sh`.** No account, no new dependency (`cloudflared` is a program, not a package), no inbound port. The address changes each run; a named tunnel on an owned domain would give a stable one and is not set up. The script keeps the Mac awake while it runs.
4. **Basic auth, not a login page.** One small piece of code, the browser remembers the password for the session, and it covers the static files and every API call alike. Over the tunnel it travels inside HTTPS.

## Limits (stated, not hidden)

- The Mac must be on, awake and online with the script running. Live Practice games are in memory, so a restart ends them.
- The password protects against strangers guessing the address, not against someone who is given the password. The address is public but unguessable; the password is the only guard, hence 12 characters minimum and the lock.
- This is the whole app, including the coach spending the model budget; the `MONTHLY_BUDGET_USD` stop still applies.
- Office networks may block `trycloudflare.com`; then nothing here works from there and the alternative is hosting (not built).
- One owner: no accounts, no per-user data (still true of the whole app).
