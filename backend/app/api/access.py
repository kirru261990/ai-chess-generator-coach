"""Password gate for reaching the app from outside this Mac (docs/remote-access.md, ADR 0023).

A request counts as local only when it names a loopback host and carries no proxy header; a tunnel adds `Host: <its address>` and
`cf-connecting-ip` / `x-forwarded-for`, so everything arriving through one is remote. Remote requests need the access password
(HTTP Basic, any user name; the browser asks once and repeats it). With no password set the remote door stays shut: the app holds
the player's games and spends the model budget, so it never opens by default. The password is stored as a scrypt hash in
`data/access.json` (git-ignored), compared in constant time, and five wrong tries lock remote access for 15 minutes (one owner, so
the counter is global). Set it with `uv run python -m app.api.access set`.
"""

import base64
import getpass
import hashlib
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.mcp.auth import check_password_hash, hash_password

ROOT = Path(__file__).resolve().parents[3]
# "testserver" is the host name FastAPI's test client uses; a tunnel always adds a proxy header, so it cannot be used to skip the gate.
LOOPBACK = {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"}
PROXY_HEADERS = (b"cf-connecting-ip", b"x-forwarded-for", b"forwarded", b"cf-ray", b"x-forwarded-host")
MAX_FAILS = 5
LOCK_SECONDS = 15 * 60


def access_file() -> Path:
    return ROOT / "data" / "access.json"


def set_password(password: str, path: Path | None = None) -> None:
    p = path or access_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"password": hash_password(password)}))
    p.chmod(0o600)


def stored_hash(path: Path | None = None) -> str | None:
    p = path or access_file()
    try:
        value = json.loads(p.read_text()).get("password")
    except (OSError, ValueError):
        return None
    return value if isinstance(value, str) and value else None


def is_remote(scope: Scope) -> bool:
    headers = dict(scope.get("headers") or [])
    host = headers.get(b"host", b"").decode("latin-1").lower()
    name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
    if name not in LOOPBACK:
        return True
    return any(h in headers for h in PROXY_HEADERS)


class AccessGate:
    """ASGI middleware: local requests pass; remote ones need the password."""

    def __init__(self, app: ASGIApp, path: Path | None = None, clock: Callable[[], float] = time.time):
        self.app, self.path, self.clock = app, path, clock
        self.fails = 0
        self.locked_until = 0.0
        self.accepted: set[str] = set()  # sha256 of an Authorization value that already passed (scrypt is slow, the browser repeats it)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket") or not is_remote(scope):
            return await self.app(scope, receive, send)
        denied = self.check(dict(scope.get("headers") or []).get(b"authorization", b"").decode("latin-1"))
        if denied is None:
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        await denied(scope, receive, send)

    def check(self, authorization: str) -> PlainTextResponse | None:
        stored = stored_hash(self.path)
        if stored is None:
            return PlainTextResponse("Remote access is off. On the Mac run: uv run python -m app.api.access set", 503)
        if self.clock() < self.locked_until:
            return PlainTextResponse("Too many wrong passwords. Try again in 15 minutes.", 429)
        key = hashlib.sha256((stored + authorization).encode()).hexdigest()
        if key in self.accepted:
            return None
        if self._password_ok(stored, authorization):
            self.fails = 0
            self.accepted.add(key)
            return None
        if authorization:  # a first visit with no credentials is just the browser asking for the login box
            self.fails += 1
            if self.fails >= MAX_FAILS:
                self.fails, self.locked_until = 0, self.clock() + LOCK_SECONDS
        return PlainTextResponse("Password needed", 401, {"WWW-Authenticate": 'Basic realm="AI Chess Coach", charset="UTF-8"'})

    @staticmethod
    def _password_ok(stored: str, authorization: str) -> bool:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "basic" or not token:
            return False
        try:
            _, _, password = base64.b64decode(token, validate=True).decode().partition(":")
        except ValueError:
            return False
        return check_password_hash(stored, password)


def main(argv: list[str]) -> int:
    if argv[:1] != ["set"]:
        print("usage: python -m app.api.access set   (choose the password for reaching the app from outside this Mac)")
        return 2
    first = getpass.getpass("New access password (12+ characters): ")
    if len(first) < 12:
        print("Too short: use at least 12 characters (anyone on the internet can try it).")
        return 1
    if getpass.getpass("Again: ") != first:
        print("They did not match; nothing saved.")
        return 1
    set_password(first)
    print(f"Saved (hashed) in {access_file()}. Remote access is now on for anyone who knows it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
