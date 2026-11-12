# Practising from another computer (the office)

Why and the limits: `docs/decisions/0023-remote-access.md`.

## Once

```bash
cd backend
uv run python -m app.api.access set      # hidden prompt, 12+ characters; stored hashed in data/access.json
brew install cloudflared                 # if `which cloudflared` finds nothing
```

## Each time (at home, before you leave, or from the office if the Mac is left on)

```bash
./scripts/office.sh
```

It builds the web app, starts the API on port 8001 (change with `OFFICE_PORT`) and prints an address like
`https://random-words.trycloudflare.com`. Leave the window open; the Mac stays awake while it runs. Ctrl-C stops it.

Open that address in the office browser, enter any user name and the password, then use Practice and Openings as usual. The
address is new on every run, so copy it somewhere you can reach from the office (a message to yourself).

## Notes

- Your normal setup (`pnpm dev` on 5173, the API on 8000) is unaffected: this runs on its own port, and requests from this Mac
  need no password.
- Build the web app only through the script (`VITE_API_URL` must be empty, or the page calls the office computer's own localhost). After a run `web/dist` exists, so your port-8000 API also serves that page; harmless.
- Wrong password five times locks the remote door for 15 minutes. A browser already signed in keeps working during a lock (so a stranger cannot cut you off), but a new sign-in waits. Restarting the script clears the lock.
- Change the password by running the `set` command again (it takes effect at once). Delete `data/access.json` to shut the remote
  door completely.
- A game you started stays in the Mac's memory only: restarting the script ends it. Opening drills are saved as usual.
- If the office network blocks `trycloudflare.com`, the page will not load there. There is no workaround in this setup.
