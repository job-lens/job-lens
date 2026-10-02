from datetime import timedelta

import pytest
import test_postgres as postgres_fixtures
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import hash_password, token_digest
from app.infrastructure.db import utcnow
from app.main import create_app
from app.modules.identity.models import Preferences, Profile, SessionRecord, User, UserRole
from app.modules.identity.service import session_record
from fastapi.testclient import TestClient
from sqlalchemy import select

database = postgres_fixtures.database
db = postgres_fixtures.db

pytestmark = pytest.mark.postgres


@pytest.fixture
def client(db):
    settings = Settings(
        database_url=str(db.engine.url),
        public_origin="https://testserver",
        trusted_hosts=["testserver"],
        environment="test",
        _env_file=None,
    )
    with TestClient(create_app(settings, db), base_url="https://testserver") as client:
        yield client


def seed(db, active=True):
    with db.transaction() as s:
        u = User(
            login_name="learner", password_hash=hash_password("training-password"), active=active
        )
        s.add(u)
        s.flush()
        s.add_all(
            [
                UserRole(user_id=u.id, role="learner"),
                Profile(user_id=u.id, display_name="测试学员"),
                Preferences(user_id=u.id),
            ]
        )
        return u.id


def csrf(client):
    r = client.get("/api/v1/auth/csrf")
    assert r.status_code == 200
    return {"Origin": "https://testserver", "X-CSRF-Token": r.json()["csrf_token"]}


def login(client):
    return client.post(
        "/api/v1/auth/login",
        headers=csrf(client),
        json={"login_name": "learner", "password": "training-password"},
    )


def test_login_rotates_cookie_csrf_and_logout_revokes(db, client):
    seed(db)
    headers = csrf(client)
    anonymous = client.cookies.get("__Host-jl_session")
    r = client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"login_name": "learner", "password": "training-password"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["roles"] == ["learner"]
    token = client.cookies.get("__Host-jl_session")
    assert token != anonymous
    assert r.json()["csrf_token"] != headers["X-CSRF-Token"]
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    assert "Domain=" not in cookie and "Path=/" in cookie
    assert client.get("/api/v1/me").status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 403
    current = {"Origin": "https://testserver", "X-CSRF-Token": r.json()["csrf_token"]}
    assert client.post("/api/v1/auth/logout", headers=current).status_code == 204
    client.cookies.set("__Host-jl_session", token)
    assert client.get("/api/v1/me").status_code == 401
    with db.transaction() as s:
        record = s.scalar(
            select(SessionRecord).where(SessionRecord.token_hash == token_digest(token))
        )
        assert record.revoked_at is not None


def test_login_is_uniform_and_requires_origin_and_csrf(db, client):
    seed(db)
    headers = csrf(client)
    body = {"login_name": "learner", "password": "incorrect"}
    assert client.post("/api/v1/auth/login", json=body).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/login", headers={**headers, "Origin": "https://evil.invalid"}, json=body
        ).status_code
        == 403
    )
    bad = client.post("/api/v1/auth/login", headers=headers, json=body)
    absent = client.post(
        "/api/v1/auth/login", headers=headers, json={**body, "login_name": "absent"}
    )
    assert bad.status_code == absent.status_code == 401
    assert bad.json()["code"] == absent.json()["code"] == "INVALID_CREDENTIALS"


def test_disabled_user_and_expired_session_cannot_authenticate(db, client):
    user_id = seed(db, active=False)
    assert login(client).status_code == 401
    with db.transaction() as s:
        s.get(User, user_id).active = True
    assert login(client).status_code == 200
    token = client.cookies.get("__Host-jl_session")
    with db.transaction() as s:
        r = s.scalar(select(SessionRecord).where(SessionRecord.token_hash == token_digest(token)))
        r.last_seen_at = utcnow() - timedelta(hours=3)
    assert client.get("/api/v1/me").status_code == 401


def test_preferences_and_profile_are_personal_and_versioned(db, client):
    seed(db)
    assert client.get("/api/v1/me/profile").status_code == 401
    result = login(client)
    assert result.status_code == 200
    headers = {"Origin": "https://testserver", "X-CSRF-Token": result.json()["csrf_token"]}
    for path, update in [
        (
            "preferences",
            {
                "font_scale": 1.25,
                "volume": 0,
                "quiet_mode": True,
                "speech_enabled": False,
                "vibration_enabled": False,
            },
        ),
        (
            "profile",
            {
                "display_name": "新的姓名",
                "sensory_preferences": [],
                "communication_preference": "文字",
                "work_notes": "",
            },
        ),
    ]:
        url = "/api/v1/me/" + path
        current = client.get(url)
        assert current.status_code == 200 and current.headers["etag"] == '"1"'
        assert client.put(url, headers=headers, json=update).status_code == 428
        saved = client.put(url, headers={**headers, "If-Match": '"1"'}, json=update)
        assert saved.status_code == 200 and saved.json()["version"] == 2
        assert saved.headers["etag"] == '"2"'
        assert (
            client.put(url, headers={**headers, "If-Match": '"1"'}, json=update).status_code == 412
        )
        assert client.put(url, headers={"If-Match": '"2"'}, json=update).status_code == 403
    assert client.get("/api/v1/capabilities").json()["realtime_calls"] is False


def test_login_attempt_limit_persists_after_csrf_refresh(db, client):
    seed(db)
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/login",
                headers=csrf(client),
                json={"login_name": "learner", "password": "wrong-password"},
            ).status_code
            == 401
        )
    assert login(client).status_code == 429


def test_incomplete_account_cannot_create_authenticated_session(db, client):
    with db.transaction() as s:
        s.add(User(login_name="learner", password_hash=hash_password("training-password")))
    result = login(client)
    assert result.status_code == 401 and result.json()["code"] == "INVALID_CREDENTIALS"
    with db.transaction() as s:
        assert s.scalar(select(SessionRecord).where(SessionRecord.user_id.is_not(None))) is None


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/me"),
        ("get", "/me/profile"),
        ("get", "/me/preferences"),
        ("get", "/capabilities"),
        ("post", "/auth/logout"),
    ],
)
def test_private_identity_endpoints_reject_anonymous(client, method, path):
    response = client.request(method, "/api/v1" + path)
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_profile_payload_cannot_choose_another_user(db, client):
    seed(db)
    with db.transaction() as s:
        other = User(login_name="other", password_hash=hash_password("training-password"))
        s.add(other)
        s.flush()
        other_id = other.id
        s.add(Profile(user_id=other_id, display_name="另一学员"))
    grant = login(client).json()
    response = client.put(
        "/api/v1/me/profile",
        headers={
            "Origin": "https://testserver",
            "X-CSRF-Token": grant["csrf_token"],
            "If-Match": '"1"',
        },
        json={
            "user_id": str(other_id),
            "display_name": "越权修改",
            "sensory_preferences": [],
            "communication_preference": "",
            "work_notes": "",
        },
    )
    assert response.status_code == 422
    with db.transaction() as s:
        assert s.get(Profile, other_id).display_name == "另一学员"


def test_cross_origin_cannot_obtain_csrf_session(client):
    response = client.get("/api/v1/auth/csrf", headers={"Origin": "https://evil.invalid"})
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_revoke_committed_after_an_initial_read_is_still_enforced(db, client):
    seed(db)
    assert login(client).status_code == 200
    token = client.cookies.get("__Host-jl_session")
    with db.sessions() as reader:
        cached = reader.scalar(
            select(SessionRecord).where(SessionRecord.token_hash == token_digest(token))
        )
        assert cached.revoked_at is None
        with db.transaction() as revoker:
            revoker.get(SessionRecord, cached.id).revoked_at = utcnow()
        with pytest.raises(AppError) as denied:
            session_record(reader, token, utcnow())
        assert denied.value.status == 401
