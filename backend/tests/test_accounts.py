import io
import json
import time
from datetime import timedelta

import mongomock
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.auth import COOKIE_NAME, LoginLimiter
from api.settings import Settings, SettingsError, load_settings
from app_db import passwords, sessions, users
from app_db.clock import utc_now
from app_db.connection import ensure_indexes
from app_db.licences import describe_storage
from repo_fetcher.github import FetchError
from repo_fetcher.licence import MAX_LICENCE_BYTES, fetch_licence

ORIGIN = "http://localhost:5173"
EMAIL = "ashish@example.com"
PASSWORD = "correct horse"


@pytest.fixture
def db():
    database = mongomock.MongoClient().vedix
    ensure_indexes(database)
    return database


def make_client(**changes):
    database = mongomock.MongoClient().vedix
    app = create_app(Settings(**changes), database=database)
    return TestClient(app), database


def register(client, email=EMAIL, password=PASSWORD, name="Ashish", headers=None):
    return client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
        headers=headers,
    )


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


# ---------- passwords ----------

def test_password_hashing():
    first = passwords.hash_password(PASSWORD)
    second = passwords.hash_password(PASSWORD)

    assert first != second  # every hash has its own random salt
    assert PASSWORD not in first
    assert first.startswith("$argon2")
    assert passwords.verify(first, PASSWORD) is True
    assert passwords.verify(first, "wrong") is False
    assert passwords.verify(None, "anything") is False
    assert passwords.verify(None, "not-a-real-password") is False  # the dummy password must not pass
    assert passwords.verify("not a hash", "x") is False


# ---------- users ----------

def test_create_and_find_users(db):
    user = users.create_user(db, "  Ashish  ", " Ashish@Example.COM ", PASSWORD)

    assert user["email"] == EMAIL
    assert user["name"] == "Ashish"
    assert user["password_hash"].startswith("$argon2")
    assert users.find_by_email(db, "ASHISH@example.com")["_id"] == user["_id"]
    assert users.find_by_email(db, "nobody@example.com") is None
    assert users.public_user(user) == {"id": str(user["_id"]), "name": "Ashish", "email": EMAIL}
    assert PASSWORD not in json.dumps(list(db["users"].find()), default=str)


def test_duplicate_email_is_refused(db):
    users.create_user(db, "A", EMAIL, PASSWORD)

    with pytest.raises(users.DuplicateEmail):
        users.create_user(db, "B", "ASHISH@example.com", "another password")

    assert db["users"].count_documents({}) == 1


def test_delete_account_removes_everything_of_that_user(db):
    first = users.create_user(db, "A", "a@example.com", PASSWORD)
    second = users.create_user(db, "B", "b@example.com", PASSWORD)
    for owner in (first, second):
        sessions.create_session(db, owner["_id"], days=7)
        for name in users.USER_COLLECTIONS[1:]:
            db[name].insert_one({"user_id": owner["_id"]})

    users.delete_account(db, first["_id"])

    assert db["users"].count_documents({}) == 1
    for name in users.USER_COLLECTIONS:
        assert db[name].count_documents({"user_id": first["_id"]}) == 0
        assert db[name].count_documents({"user_id": second["_id"]}) == 1


# ---------- sessions ----------

def test_sessions(db):
    user = users.create_user(db, "A", EMAIL, PASSWORD)

    token = sessions.create_session(db, user["_id"], days=7)

    assert len(token) >= 40
    stored = db["sessions"].find_one({})
    assert stored["_id"] != token  # only a hash is stored
    assert token not in json.dumps(stored, default=str)
    assert sessions.get_user_by_token(db, token)["_id"] == user["_id"]
    assert sessions.get_user_by_token(db, token + "x") is None
    for bad in (None, "", "x" * 500, 12345):
        assert sessions.get_user_by_token(db, bad) is None


def test_sessions_expire_and_can_be_deleted(db):
    user = users.create_user(db, "A", EMAIL, PASSWORD)
    now = utc_now()
    token = sessions.create_session(db, user["_id"], days=7, now=now)

    assert sessions.get_user_by_token(db, token, now=now + timedelta(days=6)) is not None
    assert sessions.get_user_by_token(db, token, now=now + timedelta(days=8)) is None

    sessions.delete_session(db, token)
    assert sessions.get_user_by_token(db, token, now=now) is None
    assert db["sessions"].count_documents({}) == 0


# ---------- the sign-in limiter ----------

def test_login_limiter():
    now = [0.0]
    limiter = LoginLimiter(max_failures=3, window_seconds=100, max_keys=2, clock=lambda: now[0])
    key = ("1.2.3.4", EMAIL)

    assert limiter.blocked(key) is False
    for _ in range(3):
        limiter.record_failure(key)
    assert limiter.blocked(key) is True

    now[0] = 101.0  # the failures are older than the window
    assert limiter.blocked(key) is False

    for _ in range(3):
        limiter.record_failure(key)
    limiter.reset(key)
    assert limiter.blocked(key) is False

    one = LoginLimiter(max_failures=1, max_keys=2, clock=lambda: now[0])
    for name in ("k1", "k2", "k3"):
        one.record_failure(name)
    assert one.blocked("k1") is False  # the oldest key was dropped to make room
    assert one.blocked("k2") is True
    assert one.blocked("k3") is True


# ---------- the licence rule ----------

def test_storage_decision():
    def licence(status, spdx_id=None):
        return {"status": status, "spdx_id": spdx_id, "name": None}

    assert describe_storage("upload", None)["storage"] == "full"
    assert describe_storage("upload", licence("none"))["storage"] == "full"

    for spdx_id in ["MIT", "Apache-2.0", "BSD-3-Clause", "GPL-3.0", "GPL-3.0-or-later",
                    "AGPL-3.0-only", "MPL-2.0", "Unlicense"]:
        assert describe_storage("github", licence("found", spdx_id))["storage"] == "full", spdx_id

    for spdx_id in ["NOASSERTION", "Proprietary", "", None]:
        assert describe_storage("github", licence("found", spdx_id))["storage"] == "link_only", spdx_id

    assert "No licence was found" in describe_storage("github", licence("none"))["reason"]
    assert "could not be checked" in describe_storage("github", licence("error"))["reason"]
    assert describe_storage("github", None)["storage"] == "link_only"
    assert "not recognise" in describe_storage("github", licence("found", "NOASSERTION"))["reason"]
    assert "not on our list" in describe_storage("github", licence("found", "Proprietary"))["reason"]


# ---------- asking GitHub for the licence ----------

def answer(status, body=b""):
    return lambda url: (status, {}, io.BytesIO(body) if status == 200 else None)


def mit_body():
    return json.dumps(
        {"license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT", "url": "x"}}
    ).encode("utf-8")


def test_licence_lookup_results():
    asked = []

    def open_url(url):
        asked.append(url)
        return 200, {}, io.BytesIO(mit_body())

    assert fetch_licence("octocat", "Hello-World", open_url) == {
        "status": "found", "spdx_id": "MIT", "name": "MIT License"}
    assert asked == ["https://api.github.com/repos/octocat/Hello-World/license"]

    assert fetch_licence("o", "r", answer(404))["status"] == "none"
    assert fetch_licence("o", "r", answer(200, b'{"license": null}'))["status"] == "none"

    other = fetch_licence("o", "r", answer(200, b'{"license": {"spdx_id": "NOASSERTION", "name": "Other"}}'))
    assert other == {"status": "found", "spdx_id": "NOASSERTION", "name": "Other"}


def test_licence_lookup_never_raises():
    for status in (301, 403, 429, 500):
        assert fetch_licence("o", "r", answer(status))["status"] == "error"

    bad_bodies = [b"not json", b"[1, 2]", b'{"nothing": 1}', b'{"license": 5}',
                  b"x" * (MAX_LICENCE_BYTES + 1)]
    for body in bad_bodies:
        assert fetch_licence("o", "r", answer(200, body))["status"] == "error"

    def refuses(url):
        raise FetchError("Cannot reach GitHub.")

    def broken(url):
        raise OSError("down")

    class BrokenStream:
        closed = False

        def read(self, size):
            raise OSError("lost")

        def close(self):
            self.closed = True

    stream = BrokenStream()
    assert fetch_licence("o", "r", refuses)["status"] == "error"
    assert fetch_licence("o", "r", broken)["status"] == "error"
    assert fetch_licence("o", "r", lambda url: (200, {}, stream))["status"] == "error"
    assert stream.closed is True


# ---------- the account routes ----------

def test_register_login_and_logout():
    client, db = make_client()

    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name", "email"}
    assert (body["name"], body["email"]) == ("Ashish", EMAIL)

    cookie = response.headers["set-cookie"].lower()
    assert f"{COOKIE_NAME}=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "max-age=604800" in cookie  # 7 days
    assert "secure" not in cookie

    assert client.get("/auth/me").json() == body
    assert PASSWORD not in json.dumps(list(db["users"].find()), default=str)

    out = client.post("/auth/logout")
    assert out.status_code == 204
    assert client.get("/auth/me").status_code == 401
    assert db["sessions"].count_documents({}) == 0

    again = login(client, email="ASHISH@example.com")
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]
    assert client.get("/auth/me").status_code == 200


def test_register_rules():
    client, db = make_client()

    cases = [
        ({"name": "A", "email": "abc", "password": PASSWORD}, "valid email"),
        ({"name": "  ", "email": EMAIL, "password": PASSWORD}, "your name"),
        ({"name": "A", "email": EMAIL, "password": "short"}, "at least 8"),
        ({"name": "A", "email": EMAIL, "password": "x" * 129}, "128"),
        ({}, "name, email and password"),
    ]
    for payload, fragment in cases:
        response = client.post("/auth/register", json=payload)
        assert response.status_code == 422
        assert fragment in response.json()["detail"]
    assert db["users"].count_documents({}) == 0

    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert register(client, email="ASHISH@Example.com").status_code == 409
    assert db["users"].count_documents({}) == 1


def test_wrong_passwords_are_slowed_down():
    client, _ = make_client()
    register(client)
    client.cookies.clear()

    unknown = login(client, email="nobody@example.com")
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == "Wrong email or password."

    for _ in range(5):
        wrong = login(client, password="not the password")
        assert wrong.status_code == 401
        assert wrong.json()["detail"] == "Wrong email or password."

    blocked = login(client, password="not the password")
    assert blocked.status_code == 429
    assert "Too many" in blocked.json()["detail"]
    assert login(client).status_code == 429  # even the right password waits


def test_a_session_is_needed():
    client, db = make_client()

    missing = client.get("/auth/me")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Please sign in."

    client.cookies.set(COOKIE_NAME, "garbage")
    assert client.get("/auth/me").status_code == 401

    client.cookies.clear()
    register(client)
    assert client.get("/auth/me").status_code == 200
    db["sessions"].update_many({}, {"$set": {"expires_at": utc_now() - timedelta(days=1)}})
    assert client.get("/auth/me").status_code == 401  # expired


def test_unknown_origins_are_refused():
    client, _ = make_client()
    register(client)

    assert client.post("/auth/logout", headers={"Origin": "http://evil.example"}).status_code == 403
    assert client.get("/auth/me").status_code == 200  # still signed in
    assert login(client).status_code == 200
    evil = client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD},
        headers={"Origin": "http://evil.example"},
    )
    assert evil.status_code == 403
    assert register(client, email="b@example.com", headers={"Origin": "http://evil.example"}).status_code == 403

    assert client.post("/auth/logout", headers={"Origin": ORIGIN}).status_code == 204


def test_delete_account():
    client, db = make_client()

    nobody = client.request("DELETE", "/auth/account", json={"password": PASSWORD})
    assert nobody.status_code == 401

    register(client)
    wrong = client.request("DELETE", "/auth/account", json={"password": "wrong password"})
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Wrong password."
    assert db["users"].count_documents({}) == 1

    done = client.request("DELETE", "/auth/account", json={"password": PASSWORD})
    assert done.status_code == 204
    assert db["users"].count_documents({}) == 0
    assert db["sessions"].count_documents({}) == 0
    assert client.get("/auth/me").status_code == 401


def test_accounts_need_a_database():
    client = TestClient(create_app(Settings()))

    response = register(client)
    assert response.status_code == 400
    assert "not set up" in response.json()["detail"]
    assert client.get("/auth/me").status_code == 400
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/health").status_code == 200


def test_cookie_settings_are_used():
    client, _ = make_client(cookie_secure=True, cookie_samesite="none", session_days=1)

    cookie = register(client).headers["set-cookie"].lower()

    assert "secure" in cookie
    assert "samesite=none" in cookie
    assert "max-age=86400" in cookie
    assert "httponly" in cookie


# ---------- the licence in the repository status ----------

def fake_repository(licence_answer):
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as target:
        target.writestr("r-HEAD/app.py", "x = 1\n")
    data = buffer.getvalue()

    def open_url(url):
        if url.startswith("https://api.github.com/"):
            status, body = licence_answer
            return status, {}, (io.BytesIO(body) if status == 200 else None)
        if url.startswith("https://github.com/"):
            return 302, {"Location": "https://codeload.github.com/o/r/zip/HEAD"}, None
        return 200, {"Content-Length": str(len(data))}, io.BytesIO(data)
    return open_url


def fetch_status(licence_answer):
    client = TestClient(create_app(Settings(), open_url=fake_repository(licence_answer)))
    started = client.post("/repositories", json={"url": "https://github.com/o/r"}).json()
    for _ in range(100):
        body = client.get(f"/repositories/{started['id']}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("the fetch did not finish")


def test_the_licence_decides_how_a_repository_is_stored():
    mit = fetch_status((200, mit_body()))
    assert mit["licence"]["spdx_id"] == "MIT"
    assert mit["storage"] == "full"

    none = fetch_status((404, b""))
    assert none["licence"] == {"status": "none", "spdx_id": None, "name": None}
    assert none["storage"] == "full"
    assert "No licence was found" in none["storage_reason"]

    unknown = fetch_status((200, b'{"license": {"spdx_id": "NOASSERTION", "name": "Other"}}'))
    assert unknown["storage"] == "link_only"

    limited = fetch_status((403, b""))
    assert limited["licence"]["status"] == "error"
    assert limited["storage"] == "link_only"
    assert limited["status"] == "done"  # a licence problem does not stop the fetch


# ---------- settings ----------

def test_settings_for_accounts():
    assert load_settings({}) == Settings()
    assert Settings().mongo_uri == ""
    assert Settings().session_days == 7
    assert Settings().cookie_secure is False

    settings = load_settings({
        "MONGODB_URI": "mongodb://admin:s3cretpw@db.example.com:27017",
        "MONGODB_DB": "vedix_test",
        "VEDIX_COOKIE_SECURE": "true",
        "VEDIX_COOKIE_SAMESITE": "None",
        "VEDIX_SESSION_DAYS": "3",
    })
    assert settings.mongo_uri == "mongodb://admin:s3cretpw@db.example.com:27017"
    assert (settings.mongo_db, settings.cookie_secure) == ("vedix_test", True)
    assert (settings.cookie_samesite, settings.session_days) == ("none", 3)
    assert "s3cretpw" not in repr(settings)  # the password stays out of logs
    assert "db.example.com" not in repr(settings)

    bad = [
        {"MONGODB_URI": "http://x"},
        {"MONGODB_URI": "mongodb://a b"},
        {"MONGODB_DB": "bad name!"},
        {"VEDIX_COOKIE_SAMESITE": "wrong"},
        {"VEDIX_COOKIE_SAMESITE": "none"},  # needs secure
        {"VEDIX_SESSION_DAYS": "0"},
    ]
    for environ in bad:
        with pytest.raises(SettingsError):
            load_settings(environ)

    with pytest.raises(SettingsError) as info:
        load_settings({"MONGODB_URI": "http://user:secret@x"})
    assert "secret" not in str(info.value)