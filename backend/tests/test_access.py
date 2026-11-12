import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import access

PASSWORD = "correct horse battery"


def basic(password: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"me:{password}".encode()).decode()}


@pytest.fixture
def make(tmp_path):
    def build(password: str | None = PASSWORD, clock=lambda: 0.0):
        path = tmp_path / "access.json"
        if password:
            access.set_password(password, path)
        app = FastAPI()
        app.add_middleware(access.AccessGate, path=path, clock=clock)

        @app.get("/ping")
        def ping():
            return {"ok": True}

        return app

    return build


LOCAL = "http://localhost:8000"
REMOTE = "https://random-words.trycloudflare.com"


def test_local_requests_need_no_password(make):
    assert TestClient(make(), base_url=LOCAL).get("/ping").status_code == 200


def test_remote_host_needs_the_password(make):
    c = TestClient(make(), base_url=REMOTE)
    r = c.get("/ping")
    assert r.status_code == 401 and "Basic" in r.headers["www-authenticate"]
    assert c.get("/ping", headers=basic("wrong")).status_code == 401
    assert c.get("/ping", headers=basic(PASSWORD)).json() == {"ok": True}


def test_a_proxy_header_makes_a_loopback_host_remote(make):
    # a tunnel that forwards the Host as localhost must still be gated
    c = TestClient(make(), base_url=LOCAL)
    assert c.get("/ping", headers={"cf-connecting-ip": "203.0.113.9"}).status_code == 401
    assert c.get("/ping", headers={"x-forwarded-for": "203.0.113.9", **basic(PASSWORD)}).status_code == 200


def test_remote_stays_shut_until_a_password_is_set(make):
    r = TestClient(make(password=None), base_url=REMOTE).get("/ping", headers=basic("anything at all"))
    assert r.status_code == 503 and "access" in r.text
    assert TestClient(make(password=None), base_url=LOCAL).get("/ping").status_code == 200


def test_only_basic_with_the_right_password_passes(make):
    c = TestClient(make(), base_url=REMOTE)
    assert c.get("/ping", headers={"Authorization": "Bearer " + PASSWORD}).status_code == 401
    assert c.get("/ping", headers={"Authorization": "Basic !!notbase64"}).status_code == 401


def test_five_wrong_tries_lock_remote_access_then_it_reopens(make):
    now = [0.0]
    c = TestClient(make(clock=lambda: now[0]), base_url=REMOTE)
    for _ in range(5):
        assert c.get("/ping", headers=basic("nope")).status_code == 401
    assert c.get("/ping", headers=basic(PASSWORD)).status_code == 429  # even the right one waits
    now[0] = access.LOCK_SECONDS + 1
    assert c.get("/ping", headers=basic(PASSWORD)).status_code == 200


def test_asking_for_the_login_box_is_not_a_failed_try(make):
    c = TestClient(make(), base_url=REMOTE)
    for _ in range(10):
        assert c.get("/ping").status_code == 401
    assert c.get("/ping", headers=basic(PASSWORD)).status_code == 200


def test_the_password_is_stored_hashed(tmp_path):
    path = tmp_path / "access.json"
    access.set_password(PASSWORD, path)
    assert PASSWORD not in path.read_text() and access.stored_hash(path).startswith("scrypt$")


def test_the_real_app_is_gated_from_outside(tmp_path, monkeypatch):
    from app.api.main import app

    monkeypatch.setattr(access, "access_file", lambda: tmp_path / "none.json")
    remote = TestClient(app, base_url=REMOTE)
    assert remote.get("/usage").status_code == 503  # no password set: shut
    assert remote.post("/games", json={}).status_code == 503
    assert TestClient(app, base_url=LOCAL).get("/usage").status_code == 200  # this Mac is unaffected


def test_a_stranger_cannot_lock_out_a_session_that_already_passed(make):
    c = TestClient(make(), base_url=REMOTE)
    assert c.get("/ping", headers=basic(PASSWORD)).status_code == 200
    for _ in range(5):
        c.get("/ping", headers=basic("nope"))
    assert c.get("/ping", headers=basic("nope")).status_code == 429
    assert c.get("/ping", headers=basic(PASSWORD)).status_code == 200  # the owner's open session carries on


def test_a_loopback_host_from_a_network_client_is_remote(make):
    c = TestClient(make(), base_url=LOCAL, client=("203.0.113.9", 4000))
    assert c.get("/ping").status_code == 401


def test_a_short_password_is_refused(tmp_path):
    with pytest.raises(ValueError):
        access.set_password("short", tmp_path / "a.json")


def test_static_app_is_served_after_the_api_routes(tmp_path):
    from fastapi.staticfiles import StaticFiles

    (tmp_path / "index.html").write_text("<p>web</p>")
    app = FastAPI()

    @app.get("/usage")
    def usage():
        return {"api": True}

    app.mount("/", StaticFiles(directory=tmp_path, html=True))
    c = TestClient(app)
    assert c.get("/usage").json() == {"api": True} and "web" in c.get("/").text
