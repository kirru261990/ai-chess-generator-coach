"""The login for the chat connector (docs/mcp-practice-plan.md §8): OAuth for one person.

The `mcp` library serves the OAuth endpoints, the token checks and the metadata; this module is the provider behind them plus one
login page. Everything is stored in `data/mcp_auth.sqlite3`, a separate file from the learning store. Codes and tokens are
random (256 bits) and **only their SHA-256 hashes are stored**. The password is set with `python -m app.mcp.setup`, stored as a
scrypt hash, compared in constant time, and five wrong tries lock the login for 15 minutes (one owner, so the counter is global
and persisted). Anything that identifies the owner or opens the server (the password, the database, the public URL) never goes
into a commit.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from collections.abc import Callable
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from app import config

SCOPE = "practice"
FILE_NAME = "mcp_auth.sqlite3"
ALLOWED_REDIRECT_HOSTS = {"claude.ai", "claude.com", "chatgpt.com", "chat.openai.com", "platform.openai.com",
                          "localhost", "127.0.0.1"}
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
PENDING_SECONDS = 600
CODE_SECONDS = 300
ACCESS_SECONDS = 3600
REFRESH_SECONDS = 30 * 24 * 3600
MAX_FAILURES = 5
LOCK_SECONDS = 900
MAX_CLIENTS = 50
MIN_PASSWORD = 12
_SCRYPT = {"n": 2**15, "r": 8, "p": 1, "maxmem": 64 * 1024 * 1024, "dklen": 32}

SCHEMA = """
CREATE TABLE IF NOT EXISTS setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS client (client_id TEXT PRIMARY KEY, info TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS pending (id TEXT PRIMARY KEY, client_id TEXT NOT NULL, params TEXT NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS code (hash TEXT PRIMARY KEY, client_id TEXT NOT NULL, data TEXT NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS token (hash TEXT PRIMARY KEY, kind TEXT NOT NULL, grant_id TEXT NOT NULL, client_id TEXT NOT NULL,
  scopes TEXT NOT NULL, resource TEXT, expires_at REAL NOT NULL);
"""


def db_path() -> Path:
    return config.DATA_DIR / FILE_NAME


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, isolation_level=None, check_same_thread=False)  # one event loop thread, but tests and workers differ
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.executescript(SCHEMA)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return conn


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


# --- the password ---------------------------------------------------------------------------------------------------------------


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def check_password_hash(stored: str, password: str) -> bool:
    try:
        scheme, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        h = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(h, expected)


def set_password(conn: sqlite3.Connection, password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"the password needs at least {MIN_PASSWORD} characters")
    conn.execute("INSERT OR REPLACE INTO setting (key, value) VALUES ('password', ?)", (hash_password(password),))
    conn.execute("DELETE FROM setting WHERE key IN ('failures', 'locked_until')")


def password_is_set(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM setting WHERE key = 'password'").fetchone() is not None


def redirect_host_ok(uri: str) -> bool:
    u = urlparse(uri)
    host = (u.hostname or "").lower()
    if host not in ALLOWED_REDIRECT_HOSTS or u.username or u.password or u.fragment:
        return False
    return u.scheme == "https" or (u.scheme == "http" and host in LOCAL_HOSTS)


# --- the provider ---------------------------------------------------------------------------------------------------------------


class PracticeAuthProvider:
    """OAuthAuthorizationServerProvider for one owner. `clock` is replaced in tests."""

    def __init__(self, public_url: str, path: Path | str | None = None, clock: Callable[[], float] = time.time):
        self.public_url = public_url.rstrip("/")
        self.resource = self.public_url + "/mcp"
        self.path = path
        self.clock = clock
        self._conn = connect(path)

    # clients
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = self._conn.execute("SELECT info FROM client WHERE client_id = ?", (client_id,)).fetchone()
        return OAuthClientInformationFull.model_validate_json(row["info"]) if row else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        uris = [str(u) for u in (client_info.redirect_uris or [])]
        if not uris or not all(redirect_host_ok(u) for u in uris):
            raise RegistrationError("invalid_redirect_uri", "this server accepts only Claude, ChatGPT and local redirect addresses")
        if client_info.client_id is None:
            raise RegistrationError("invalid_client_metadata", "no client id")
        self._conn.execute("INSERT OR REPLACE INTO client (client_id, info, created_at) VALUES (?, ?, ?)",
                           (client_info.client_id, client_info.model_dump_json(), self.clock()))
        self._conn.execute("DELETE FROM client WHERE client_id NOT IN (SELECT client_id FROM client ORDER BY created_at DESC LIMIT ?)",
                           (MAX_CLIENTS,))

    # the authorisation request: stored, then the player signs in on our page
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        if params.resource is not None and params.resource.rstrip("/") != self.resource:
            raise AuthorizeError("invalid_target", "this server issues tokens only for itself")
        if not redirect_host_ok(str(params.redirect_uri)):
            raise AuthorizeError("invalid_request", "redirect address not allowed")
        request_id = new_secret()
        now = self.clock()
        self._conn.execute("DELETE FROM pending WHERE expires_at < ?", (now,))
        data = {"state": params.state, "code_challenge": params.code_challenge, "redirect_uri": str(params.redirect_uri),
                "explicit": params.redirect_uri_provided_explicitly}
        self._conn.execute("INSERT INTO pending (id, client_id, params, expires_at) VALUES (?, ?, ?, ?)",
                           (request_id, client.client_id, json.dumps(data), now + PENDING_SECONDS))
        return f"{self.public_url}/login?request={request_id}"

    def pending(self, request_id: str) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM pending WHERE id = ? AND expires_at >= ?", (request_id, self.clock())).fetchone()

    # the password and the lock-out
    def locked_for(self) -> int:
        row = self._conn.execute("SELECT value FROM setting WHERE key = 'locked_until'").fetchone()
        left = float(row["value"]) - self.clock() if row else 0
        return int(left) + 1 if left > 0 else 0

    def try_password(self, password: str) -> str:
        """'ok', 'wrong', 'locked' or 'unset'. A right password while locked is still refused."""
        if self.locked_for():
            return "locked"
        row = self._conn.execute("SELECT value FROM setting WHERE key = 'password'").fetchone()
        if row is None:
            return "unset"
        if check_password_hash(row["value"], password):
            self._conn.execute("DELETE FROM setting WHERE key IN ('failures', 'locked_until')")
            return "ok"
        fails = self._conn.execute("SELECT value FROM setting WHERE key = 'failures'").fetchone()
        n = (int(fails["value"]) if fails else 0) + 1
        if n >= MAX_FAILURES:
            self._conn.execute("INSERT OR REPLACE INTO setting (key, value) VALUES ('locked_until', ?)", (str(self.clock() + LOCK_SECONDS),))
            self._conn.execute("DELETE FROM setting WHERE key = 'failures'")
            return "locked"
        self._conn.execute("INSERT OR REPLACE INTO setting (key, value) VALUES ('failures', ?)", (str(n),))
        return "wrong"

    def approve(self, request_id: str) -> str | None:
        """The password was right: make the single-use code and return the client's redirect address (None if the request
        expired or was already used)."""
        row = self._conn.execute("DELETE FROM pending WHERE id = ? AND expires_at >= ? RETURNING *", (request_id, self.clock())).fetchone()
        if row is None:
            return None
        p = json.loads(row["params"])
        code = new_secret()
        data = {"scopes": [SCOPE], "code_challenge": p["code_challenge"], "redirect_uri": p["redirect_uri"],
                "explicit": p["explicit"], "resource": self.resource}
        self._conn.execute("INSERT INTO code (hash, client_id, data, expires_at) VALUES (?, ?, ?, ?)",
                           (digest(code), row["client_id"], json.dumps(data), self.clock() + CODE_SECONDS))
        return construct_redirect_uri(p["redirect_uri"], code=code, state=p["state"])

    # codes and tokens
    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> AuthorizationCode | None:
        row = self._conn.execute("SELECT * FROM code WHERE hash = ? AND client_id = ?", (digest(authorization_code), client.client_id)).fetchone()
        if row is None or row["expires_at"] < self.clock():
            return None
        d = json.loads(row["data"])
        return AuthorizationCode(code=authorization_code, scopes=d["scopes"], expires_at=row["expires_at"], client_id=row["client_id"],
                                 code_challenge=d["code_challenge"], redirect_uri=d["redirect_uri"],
                                 redirect_uri_provided_explicitly=d["explicit"], resource=d["resource"])

    def _issue(self, client_id: str, scopes: list[str], grant_id: str | None = None) -> OAuthToken:
        now = self.clock()
        grant_id = grant_id or new_secret()
        access, refresh = new_secret(), new_secret()
        for secret, kind, ttl in ((access, "access", ACCESS_SECONDS), (refresh, "refresh", REFRESH_SECONDS)):
            self._conn.execute(
                "INSERT INTO token (hash, kind, grant_id, client_id, scopes, resource, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (digest(secret), kind, grant_id, client_id, " ".join(scopes), self.resource, now + ttl))
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=ACCESS_SECONDS, scope=" ".join(scopes), refresh_token=refresh)

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode) -> OAuthToken:
        # delete first: a code works once, even for two requests at once
        gone = self._conn.execute("DELETE FROM code WHERE hash = ?", (digest(authorization_code.code),)).rowcount
        if gone != 1:
            raise TokenError("invalid_grant", "the code was already used")
        return self._issue(client.client_id or "", authorization_code.scopes)

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        row = self._conn.execute("SELECT * FROM token WHERE hash = ? AND kind = 'refresh' AND client_id = ?",
                                 (digest(refresh_token), client.client_id)).fetchone()
        if row is None or row["expires_at"] < self.clock():
            return None
        return RefreshToken(token=refresh_token, client_id=row["client_id"], scopes=row["scopes"].split(), expires_at=int(row["expires_at"]),
                            resource=row["resource"])

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        row = self._conn.execute("DELETE FROM token WHERE hash = ? AND kind = 'refresh' RETURNING grant_id", (digest(refresh_token.token),)).fetchone()
        if row is None:
            raise TokenError("invalid_grant", "the refresh token was already used")
        self._conn.execute("DELETE FROM token WHERE grant_id = ?", (row["grant_id"],))  # the old access token goes with it
        return self._issue(client.client_id or "", [SCOPE], row["grant_id"])

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = self._conn.execute("SELECT * FROM token WHERE hash = ? AND kind = 'access'", (digest(token),)).fetchone()
        if row is None or row["expires_at"] < self.clock():
            return None
        return AccessToken(token=token, client_id=row["client_id"], scopes=row["scopes"].split(), expires_at=int(row["expires_at"]),
                           resource=row["resource"])

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        row = self._conn.execute("SELECT grant_id FROM token WHERE hash = ?", (digest(token.token),)).fetchone()
        if row:
            self._conn.execute("DELETE FROM token WHERE grant_id = ?", (row["grant_id"],))


# --- the login page ---------------------------------------------------------------------------------------------------------------

_FORM_ACTION = "'self' " + " ".join(f"https://{h}" for h in sorted(ALLOWED_REDIRECT_HOSTS - LOCAL_HOSTS)) + " http://localhost:* http://127.0.0.1:*"
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": f"default-src 'none'; style-src 'unsafe-inline'; form-action {_FORM_ACTION}; frame-ancestors 'none'; base-uri 'none'",
}
MAX_FORM_BYTES = 4096


def _page(body: str, status: int = 200) -> HTMLResponse:
    html = ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Chess coach sign-in</title><style>body{font:16px system-ui;max-width:28rem;margin:3rem auto;padding:0 1rem}"
            "input,button{font:inherit;padding:.5rem;width:100%;box-sizing:border-box;margin:.4rem 0}.err{color:#b00020}</style>" + body)
    return HTMLResponse(html, status_code=status, headers=SECURITY_HEADERS)


def _form(provider: PracticeAuthProvider, request_id: str, error: str | None = None, status: int = 200) -> HTMLResponse:
    row = provider.pending(request_id)
    if row is None:
        return _page("<h1>Sign-in expired</h1><p>Go back to the chat and add the connector again.</p>", 400)
    host = urlparse(json.loads(row["params"])["redirect_uri"]).hostname or "?"
    err = f"<p class=err>{escape(error)}</p>" if error else ""
    return _page(
        f"<h1>Chess coach</h1><p>An app at <b>{escape(host)}</b> asks to run your chess practice. It can do practice only: "
        f"it cannot take your tests.</p>{err}<form method=post action='/login'>"
        f"<input type=hidden name=request value='{escape(request_id, quote=True)}'>"
        "<label>Password<input type=password name=password autocomplete=current-password autofocus required></label>"
        "<button type=submit>Sign in</button></form>", status)


def register_login(mcp, provider: PracticeAuthProvider) -> None:
    @mcp.custom_route("/login", methods=["GET", "POST"], include_in_schema=False)
    async def login(request: Request) -> Response:
        if request.method == "GET":
            return _form(provider, request.query_params.get("request", ""))
        body = await request.body()
        if len(body) > MAX_FORM_BYTES:
            return _page("<h1>Too large</h1>", 413)
        form = parse_qs(body.decode("utf-8", "replace"))
        request_id = (form.get("request") or [""])[0]
        password = (form.get("password") or [""])[0]
        if provider.pending(request_id) is None:
            return _form(provider, request_id)
        result = provider.try_password(password)
        if result == "locked":
            minutes = max(1, provider.locked_for() // 60 + 1)
            return _form(provider, request_id, f"Too many wrong passwords. Try again in about {minutes} minutes.", 429)
        if result == "unset":
            return _form(provider, request_id, "No password has been set. Run: python -m app.mcp.setup", 503)
        if result == "wrong":
            return _form(provider, request_id, "That password is not right.", 401)
        target = provider.approve(request_id)
        if target is None:
            return _form(provider, request_id)
        return RedirectResponse(target, status_code=302, headers=SECURITY_HEADERS)
