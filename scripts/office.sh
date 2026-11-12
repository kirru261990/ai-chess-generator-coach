#!/usr/bin/env bash
# Practice from another computer (docs/remote-access.md, ADR 0023): builds the web app, serves it with the API on this Mac and opens
# a Cloudflare quick tunnel. Run from the repo root. Leave it running (it also keeps the Mac awake); Ctrl-C stops everything.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -s data/access.json ]; then
  echo "No access password yet. Set one first (12+ characters):"
  echo "  cd backend && uv run python -m app.api.access set"
  exit 1
fi
command -v cloudflared >/dev/null || { echo "Install the tunnel program first: brew install cloudflared"; exit 1; }

PORT="${OFFICE_PORT:-8001}"
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is busy. Stop what is using it, or set OFFICE_PORT=8002, then run this again."
  exit 1
fi

echo "Building the web app (same-address mode)..."
(cd web && pnpm install --frozen-lockfile >/dev/null && VITE_API_URL= pnpm exec vite build >/dev/null)

(cd backend && exec uv run uvicorn app.api.main:app --host 127.0.0.1 --port "$PORT") &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 60); do
  curl -fs "http://127.0.0.1:$PORT/usage" >/dev/null 2>&1 && break
  sleep 0.5
done

echo
echo "Starting the tunnel. Open the https://....trycloudflare.com address below on any computer;"
echo "the browser asks for a password (user name: anything), then use Practice and Openings as usual."
echo "The address changes every time you run this."
echo
caffeinate -i cloudflared tunnel --url "http://127.0.0.1:$PORT"
