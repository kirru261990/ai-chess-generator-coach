"""The connector's login, over HTTP with a Starlette test client: registration, the sign-in page, the code and token exchange with
PKCE, the lock-out, expiry, rotation, revocation, host checks, and that the stored secrets are hashes."""

import base64
import hashlib
import sqlite3
from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from app.db.schema import connect
from app.mcp import auth
from app.mcp import server as S
from tests.test_practice import FakeAnalyser, make_store

PUBLIC = "https://coach.example.com"
PASSWORD = "correct horse battery"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"


@contextmanager
def scripted(_conn):
    yield FakeAnalyser()


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path):
    store = tmp_path / "store.sqlite3"
    c = connect(store)
    make_store(c)
    c.close()
    clock = Clock()
    auth_path = tmp_path / "auth.sqlite3"
    conn = auth.connect(auth_path)
    auth.set_password(conn, PASSWORD)
    conn.close()
    app, provider = S.build_http_app(PUBLIC, auth_path=auth_path, conn_factory=lambda: connect(store), opener=scripted, clock=clock)
    with TestClient(app, base_url=PUBLIC, follow_redirects=False) as client:
        yield client, provider, clock, auth_path


def pkce():
    verifier = base64.urlsafe_b64encode(b"v" * 40).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def register(client, redirect=REDIRECT):
    return client.post("/register", json={"redirect_uris": [redirect], "token_endpoint_auth_method": "none",
                                          "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
                                          "client_name": "test"})


def start(client, client_id, challenge, redirect=REDIRECT, **extra):
    q = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect, "code_challenge": challenge,
         "code_challenge_method": "S256", "state": "xyz", **extra}
    return client.get("/authorize", params=q)


def sign_in(client, request_id, password=PASSWORD):
    return client.post("/login", content=f"request={request_id}&password={password}",
                       headers={"content-type": "application/x-www-form-urlencoded"})


def request_id_of(resp):
    return parse_qs(urlparse(resp.headers["location"]).query)["request"][0]


def full_flow(client, redirect=REDIRECT):
    cid = register(client, redirect).json()["client_id"]
    verifier, challenge = pkce()
    r = start(client, cid, challenge, redirect)
    assert r.status_code == 302 and r.headers["location"].startswith(PUBLIC + "/login?request="), r.text
    done = sign_in(client, request_id_of(r))
    assert done.status_code == 302, done.text
    loc = urlparse(done.headers["location"])
    q = parse_qs(loc.query)
    assert f"{loc.scheme}://{loc.netloc}{loc.path}" == redirect and q["state"] == ["xyz"]
    return cid, verifier, q["code"][0]


def exchange(client, cid, verifier, code, redirect=REDIRECT):
    return client.post("/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect, "client_id": cid,
                                       "code_verifier": verifier})


def tool_call(client, token, name="practice_status", args=None):
    h = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    if token:
        h["authorization"] = f"Bearer {token}"
    return client.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                                "params": {"name": name, "arguments": args or {}}})


def tokens(env):
    client, *_ = env
    cid, verifier, code = full_flow(client)
    r = exchange(client, cid, verifier, code)
    assert r.status_code == 200, r.text
    return cid, r.json()


# --- no token ------------------------------------------------------------------------------------------------------------------


def test_no_token_is_401_with_the_protected_resource_metadata(env):
    client, *_ = env
    r = tool_call(client, None)
    assert r.status_code == 401 and "resource_metadata" in r.headers["www-authenticate"]
    meta = client.get("/.well-known/oauth-protected-resource/mcp")
    assert meta.status_code == 200 and meta.json()["resource"] == PUBLIC + "/mcp"
    assert client.get("/.well-known/oauth-authorization-server").json()["registration_endpoint"] == PUBLIC + "/register"


def test_a_made_up_token_is_refused(env):
    client, *_ = env
    assert tool_call(client, "not-a-token").status_code == 401


# --- registration --------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("uri", [REDIRECT, "https://claude.com/api/mcp/auth_callback", "https://chatgpt.com/connector/oauth/abc",
                                 "https://chat.openai.com/aip/x/oauth/callback", "http://localhost:6274/oauth/callback",
                                 "http://127.0.0.1:33418/callback"])
def test_registration_accepts_the_allowed_hosts(env, uri):
    assert register(env[0], uri).status_code == 201


@pytest.mark.parametrize("uri", ["https://evil.example.com/cb", "https://claude.ai.evil.com/cb", "http://claude.ai/cb",
                                 "https://user@claude.ai/cb", "https://notclaude.ai/cb", "http://example.com/cb"])
def test_registration_refuses_other_redirects(env, uri):
    r = register(env[0], uri)
    assert r.status_code == 400 and r.json()["error"] == "invalid_redirect_uri"


# --- the sign-in and the exchange ----------------------------------------------------------------------------------------------


def test_the_full_flow_ends_with_a_working_tool_call(env):
    client, *_ = env
    _, body = tokens(env)
    assert body["token_type"].lower() == "bearer" and body["scope"] == "practice" and body["expires_in"] == 3600
    r = tool_call(client, body["access_token"])
    assert r.status_code == 200, r.text
    assert "Practice status" in r.json()["result"]["content"][0]["text"]


def test_the_login_page_names_the_client_and_has_security_headers(env):
    client, *_ = env
    cid = register(client).json()["client_id"]
    r = start(client, cid, pkce()[1])
    page = client.get("/login", params={"request": request_id_of(r)})
    assert page.status_code == 200 and "claude.ai" in page.text and "cannot take your tests" in page.text
    h = page.headers
    assert h["cache-control"] == "no-store" and h["referrer-policy"] == "no-referrer" and h["x-frame-options"] == "DENY"
    assert "default-src 'none'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]
    assert "password" not in page.text.split("value=")[1][:0]  # nothing is pre-filled


def test_a_bad_or_expired_request_id_shows_expired(env):
    client, _, clock, _ = env
    assert client.get("/login", params={"request": "nope"}).status_code == 400
    cid = register(client).json()["client_id"]
    rid = request_id_of(start(client, cid, pkce()[1]))
    clock.t += 601
    assert sign_in(client, rid).status_code == 400


def test_a_wrong_password_is_refused_and_shows_no_code(env):
    client, *_ = env
    cid = register(client).json()["client_id"]
    rid = request_id_of(start(client, cid, pkce()[1]))
    r = sign_in(client, rid, "wrong password here")
    assert r.status_code == 401 and "location" not in r.headers and "not right" in r.text


def test_five_wrong_passwords_lock_the_login_even_for_the_right_one(env):
    client, _, clock, _ = env
    cid = register(client).json()["client_id"]
    rid = request_id_of(start(client, cid, pkce()[1]))
    codes = [sign_in(client, rid, f"wrong-{i}").status_code for i in range(5)]
    assert codes == [401, 401, 401, 401, 429]
    locked = sign_in(client, rid)
    assert locked.status_code == 429 and "location" not in locked.headers
    clock.t += 901  # the lock ends (the old request has expired by then: start again)
    assert sign_in(client, rid).status_code == 400
    assert sign_in(client, request_id_of(start(client, cid, pkce()[1]))).status_code == 302


def test_a_right_password_resets_the_failure_count(env):
    client, *_ = env
    for _ in range(3):
        cid = register(client).json()["client_id"]
        rid = request_id_of(start(client, cid, pkce()[1]))
        for i in range(4):
            assert sign_in(client, rid, f"bad-{i}").status_code == 401
        assert sign_in(client, rid).status_code == 302


def test_the_lock_survives_a_restart(env, tmp_path):
    client, _, clock, path = env
    cid = register(client).json()["client_id"]
    rid = request_id_of(start(client, cid, pkce()[1]))
    for i in range(5):
        sign_in(client, rid, f"bad-{i}")
    again = auth.PracticeAuthProvider(PUBLIC, path, clock)
    assert again.try_password(PASSWORD) == "locked"


def test_a_code_works_once(env):
    client, *_ = env
    cid, verifier, code = full_flow(client)
    assert exchange(client, cid, verifier, code).status_code == 200
    assert exchange(client, cid, verifier, code).status_code == 400


def test_a_wrong_pkce_verifier_is_refused_and_the_code_is_not_spent_by_it(env):
    client, *_ = env
    cid, verifier, code = full_flow(client)
    assert exchange(client, cid, "x" * 43, code).status_code == 400
    assert exchange(client, cid, verifier, code).status_code == 200


def test_an_expired_code_is_refused(env):
    client, _, clock, _ = env
    cid, verifier, code = full_flow(client)
    clock.t += 301
    assert exchange(client, cid, verifier, code).status_code == 400


def test_a_code_cannot_be_used_by_another_client(env):
    client, *_ = env
    _, verifier, code = full_flow(client)
    other = register(client).json()["client_id"]
    assert exchange(client, other, verifier, code).status_code == 400


def test_a_token_for_another_resource_is_refused(env):
    client, provider, *_ = env
    cid = register(client).json()["client_id"]
    r = start(client, cid, pkce()[1], resource="https://other.example.com/mcp")
    assert r.status_code == 302 and "error=invalid_target" in r.headers["location"]
    # and a token stored for some other resource never passes the server's check
    token = provider._issue(cid, ["practice"])
    provider._conn.execute("UPDATE token SET resource = 'https://other.example.com/mcp'")
    assert tool_call(client, token.access_token).status_code == 401


# --- expiry, rotation, revocation -------------------------------------------------------------------------------------------


def test_an_expired_access_token_is_refused(env):
    client, _, clock, _ = env
    _, body = tokens(env)
    assert tool_call(client, body["access_token"]).status_code == 200
    clock.t += 3601
    assert tool_call(client, body["access_token"]).status_code == 401


def test_a_refresh_token_rotates_and_the_old_one_dies(env):
    client, _, clock, _ = env
    cid, body = tokens(env)
    clock.t += 3601
    r = client.post("/token", data={"grant_type": "refresh_token", "refresh_token": body["refresh_token"], "client_id": cid})
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["refresh_token"] != body["refresh_token"] and new["access_token"] != body["access_token"]
    assert tool_call(client, new["access_token"]).status_code == 200
    again = client.post("/token", data={"grant_type": "refresh_token", "refresh_token": body["refresh_token"], "client_id": cid})
    assert again.status_code == 400
    clock.t += 31 * 24 * 3600  # a refresh token lasts 30 days
    last = client.post("/token", data={"grant_type": "refresh_token", "refresh_token": new["refresh_token"], "client_id": cid})
    assert last.status_code == 400


def test_revoking_a_token_ends_the_whole_grant(env):
    # the library's /revoke asks for a client secret, so this client is a confidential one
    client, *_ = env
    reg = client.post("/register", json={"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "client_secret_post",
                                         "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}).json()
    cid, secret = reg["client_id"], reg["client_secret"]
    verifier, challenge = pkce()
    done = sign_in(client, request_id_of(start(client, cid, challenge)))
    code = parse_qs(urlparse(done.headers["location"]).query)["code"][0]
    body = client.post("/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "client_id": cid,
                                       "client_secret": secret, "code_verifier": verifier}).json()
    r = client.post("/revoke", data={"token": body["refresh_token"], "client_id": cid, "client_secret": secret})
    assert r.status_code == 200, r.text
    assert tool_call(client, body["access_token"]).status_code == 401
    assert client.post("/token", data={"grant_type": "refresh_token", "refresh_token": body["refresh_token"], "client_id": cid,
                                                        "client_secret": secret}).status_code == 400


# --- hosts and storage ---------------------------------------------------------------------------------------------------------


def test_a_foreign_host_is_refused_everywhere(env):
    client, *_ = env
    for path in ("/login?request=x", "/.well-known/oauth-authorization-server", "/mcp"):
        r = client.get(path, headers={"host": "evil.example.com"})
        assert r.status_code == 421, path
    assert client.get("/login?request=x", headers={"host": "127.0.0.1:8765"}).status_code == 400  # ours, but no such request


def test_only_hashes_are_stored(env):
    _, _, _, path = env
    _, body = tokens(env)
    raw = body["access_token"], body["refresh_token"]
    db = sqlite3.connect(path)
    dump = "\n".join(str(r) for t in ("token", "code", "pending", "setting") for r in db.execute(f"SELECT * FROM {t}"))
    for secret in (*raw, PASSWORD):
        assert secret not in dump
    assert db.execute("SELECT COUNT(*) FROM token").fetchone()[0] == 2
    assert all(len(h) == 64 for (h,) in db.execute("SELECT hash FROM token"))
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_the_password_rules(tmp_path):
    conn = auth.connect(tmp_path / "a.sqlite3")
    with pytest.raises(ValueError):
        auth.set_password(conn, "short")
    assert not auth.password_is_set(conn)
    auth.set_password(conn, PASSWORD)
    stored = conn.execute("SELECT value FROM setting WHERE key = 'password'").fetchone()[0]
    assert stored.startswith("scrypt$") and PASSWORD not in stored
    assert auth.check_password_hash(stored, PASSWORD) and not auth.check_password_hash(stored, PASSWORD + "x")
    assert not auth.check_password_hash("garbage", PASSWORD)
    assert auth.hash_password(PASSWORD) != auth.hash_password(PASSWORD)  # a random salt each time


def test_no_password_set_means_no_sign_in(tmp_path):
    p = auth.PracticeAuthProvider(PUBLIC, tmp_path / "x.sqlite3")
    assert p.try_password("anything at all") == "unset"
