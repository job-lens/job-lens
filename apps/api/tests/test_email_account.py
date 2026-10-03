import re
from datetime import timedelta

import pytest
import test_postgres as postgres_fixtures
from app.core.config import Settings
from app.core.security import token_digest
from app.infrastructure.db import utcnow
from app.main import create_app
from app.modules.identity.models import EmailChallenge, Preferences, Profile, User, UserRole
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.postgres
database = postgres_fixtures.database
db = postgres_fixtures.db


@pytest.fixture
def inbox(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.modules.identity.registration.send_email",
        lambda config, email, subject, text: sent.append((email, subject, text)),
    )
    return sent


@pytest.fixture
def client(db, inbox):
    settings = Settings(
        database_url=str(db.engine.url),
        public_origin="https://testserver",
        trusted_hosts=["testserver"],
        environment="test",
        mail_api_key="test-only-key",
        mail_from="Job Lens <test@example.invalid>",
        _env_file=None,
    )
    with TestClient(create_app(settings, db), base_url="https://testserver") as value:
        yield value


def csrf(client):
    return {
        "Origin": "https://testserver",
        "X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"],
    }


def register(client, inbox, email="student@example.invalid"):
    headers = csrf(client)
    r = client.post("/api/v1/auth/registration-code", headers=headers, json={"email": email})
    assert r.status_code == 202
    code = re.search(r"\b\d{6}\b", inbox[-1][2]).group()
    r = client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={
            "email": email,
            "code": code,
            "password": "training-password",
            "display_name": "学员",
        },
    )
    assert r.status_code == 201, r.text
    return r


def test_registration_is_real_atomic_learner_only_and_single_use(db, client, inbox):
    response = register(client, inbox, "Student@Example.invalid")
    user_id = response.json()["user"]["id"]
    assert response.json()["user"]["roles"] == ["learner"]
    assert client.get("/api/v1/me").status_code == 200
    with db.transaction() as s:
        user = s.scalar(select(User).where(User.login_name == "student@example.invalid"))
        assert str(user.id) == user_id
        assert s.get(Profile, user.id).display_name == "学员"
        assert s.get(Preferences, user.id).quiet_mode is True
        assert s.scalars(select(UserRole.role).where(UserRole.user_id == user.id)).all() == [
            "learner"
        ]
        challenge = s.scalar(select(EmailChallenge))
        assert challenge.consumed_at is not None
        assert inbox[-1][2].split("验证码：")[1][:6] not in challenge.code_hash
    code = re.search(r"\b\d{6}\b", inbox[-1][2]).group()
    replay = client.post(
        "/api/v1/auth/register",
        headers=csrf(client),
        json={
            "email": "student@example.invalid",
            "code": code,
            "password": "training-password",
            "display_name": "学员",
        },
    )
    assert replay.status_code == 400
    privileged = client.post(
        "/api/v1/auth/register",
        headers=csrf(client),
        json={
            "email": "next@example.invalid",
            "code": code,
            "password": "training-password",
            "display_name": "学员",
            "roles": ["counselor"],
        },
    )
    assert privileged.status_code == 422


def test_production_local_accounts_work_with_scanning_explicitly_disabled(db, inbox, tmp_path):
    settings = Settings(
        database_url=str(db.engine.url),
        public_origin="https://testserver",
        trusted_hosts=["testserver"],
        environment="production",
        storage_kind="local",
        storage_root=tmp_path,
        scan_enabled=False,
        mail_api_key="test-only-key",
        mail_from="Job Lens <test@example.invalid>",
        _env_file=None,
    )
    # Delivery remains the explicit inbox test double; this never contacts real email.
    with TestClient(create_app(settings, db), base_url="https://testserver") as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        register(client, inbox)
        assert client.get("/api/v1/me").status_code == 200
        client.cookies.clear()
        response = client.post(
            "/api/v1/auth/login",
            headers=csrf(client),
            json={"login_name": "student@example.invalid", "password": "training-password"},
        )
        assert response.status_code == 200
        assert client.get("/api/v1/me").status_code == 200
    assert list(tmp_path.iterdir()) == []


def test_code_attempts_expiry_resend_and_csrf(db, client, inbox):
    headers = csrf(client)
    path = "/api/v1/auth/registration-code"
    assert client.post(path, json={"email": "s@example.invalid"}).status_code == 403
    assert (
        client.post(
            path,
            headers={**headers, "Origin": "https://evil.invalid"},
            json={"email": "s@example.invalid"},
        ).status_code
        == 403
    )
    assert (
        client.post(path, headers=headers, json={"email": "s@example.invalid"}).status_code == 202
    )
    assert (
        client.post(path, headers=headers, json={"email": "s@example.invalid"}).status_code == 429
    )
    with db.transaction() as s:
        challenge = s.scalar(select(EmailChallenge))
        challenge.expires_at = utcnow() - timedelta(seconds=1)
    body = {
        "email": "s@example.invalid",
        "code": "000000",
        "password": "training-password",
        "display_name": "学员",
    }
    assert client.post("/api/v1/auth/register", headers=headers, json=body).status_code == 400
    with db.transaction() as s:
        challenge = s.scalar(select(EmailChallenge))
        challenge.expires_at = utcnow() + timedelta(minutes=5)
        challenge.code_hash = "invalid-hash"
    for _ in range(5):
        assert client.post("/api/v1/auth/register", headers=headers, json=body).status_code == 400
    with db.transaction() as s:
        assert s.scalar(select(EmailChallenge)).attempts == 5
        assert not s.scalars(select(User)).all()


def test_reset_is_single_use_revokes_all_sessions_and_hides_unknown_accounts(db, client, inbox):
    register(client, inbox)
    original = client.cookies.get("__Host-jl_session")
    headers = csrf(client)
    path = "/api/v1/auth/password-reset-requests"
    known = client.post(path, headers=headers, json={"email": "student@example.invalid"})
    known_mail = inbox[-1][2]
    unknown = client.post(path, headers=headers, json={"email": "unknown@example.invalid"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(inbox) == 3
    token = re.search(r"#token=([A-Za-z0-9_-]+)", known_mail).group(1)
    with db.transaction() as s:
        challenge = s.scalar(
            select(EmailChallenge).where(EmailChallenge.token_hash == token_digest(token))
        )
        assert challenge is not None and challenge.token_hash != token
    body = {"token": token, "password": "updated-training-password"}
    assert (
        client.post("/api/v1/auth/password-resets", headers=headers, json=body).status_code == 204
    )
    client.cookies.set("__Host-jl_session", original)
    assert client.get("/api/v1/me").status_code == 401
    client.cookies.clear()
    assert (
        client.post("/api/v1/auth/password-resets", headers=csrf(client), json=body).status_code
        == 400
    )
    headers = csrf(client)
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"login_name": "student@example.invalid", "password": "training-password"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"login_name": "student@example.invalid", "password": "updated-training-password"},
        ).status_code
        == 200
    )


def test_unconfigured_delivery_fails_without_creating_an_account_or_challenge(db):
    settings = Settings(
        database_url=str(db.engine.url),
        public_origin="https://testserver",
        trusted_hosts=["testserver"],
        environment="test",
        _env_file=None,
    )
    with TestClient(create_app(settings, db), base_url="https://testserver") as client:
        for path in ["registration-code", "password-reset-requests"]:
            r = client.post(
                "/api/v1/auth/" + path,
                headers=csrf(client),
                json={"email": "student@example.invalid"},
            )
            assert r.status_code == 503
            assert r.json()["code"] == "EMAIL_UNAVAILABLE"
    with db.transaction() as s:
        assert not s.scalars(select(EmailChallenge)).all()
        assert not s.scalars(select(User)).all()


def test_delivery_failure_rolls_back_challenge_but_keeps_cooldown(db, client, monkeypatch):
    from app.core.errors import AppError

    def fail(*args):
        raise AppError(503, "EMAIL_UNAVAILABLE", "邮件服务暂不可用")

    monkeypatch.setattr("app.modules.identity.registration.send_email", fail)
    headers = csrf(client)
    body = {"email": "s@example.invalid"}
    assert (
        client.post("/api/v1/auth/registration-code", headers=headers, json=body).status_code == 503
    )
    assert (
        client.post("/api/v1/auth/registration-code", headers=headers, json=body).status_code == 429
    )
    with db.transaction() as s:
        assert not s.scalars(select(EmailChallenge)).all()


def test_expired_and_unknown_reset_links_never_change_credentials(db, client, inbox):
    register(client, inbox)
    headers = csrf(client)
    client.post(
        "/api/v1/auth/password-reset-requests",
        headers=headers,
        json={"email": "student@example.invalid"},
    )
    token = re.search(r"#token=([A-Za-z0-9_-]+)", inbox[-1][2]).group(1)
    with db.transaction() as s:
        s.scalar(select(EmailChallenge).where(EmailChallenge.purpose == "reset")).expires_at = (
            utcnow() - timedelta(seconds=1)
        )
    for candidate in [token, "a" * 43]:
        assert (
            client.post(
                "/api/v1/auth/password-resets",
                headers=headers,
                json={"token": candidate, "password": "updated-training-password"},
            ).status_code
            == 400
        )
    with db.transaction() as s:
        assert s.scalar(select(User)).credential_version == 1


def test_reset_revokes_a_second_device_session(db, client, inbox):
    register(client, inbox)
    with TestClient(client.app, base_url="https://testserver") as other:
        result = other.post(
            "/api/v1/auth/login",
            headers=csrf(other),
            json={"login_name": "STUDENT@example.invalid", "password": "training-password"},
        )
        assert result.status_code == 200
        headers = csrf(client)
        client.post(
            "/api/v1/auth/password-reset-requests",
            headers=headers,
            json={"email": "student@example.invalid"},
        )
        token = re.search(r"#token=([A-Za-z0-9_-]+)", inbox[-1][2]).group(1)
        assert (
            client.post(
                "/api/v1/auth/password-resets",
                headers=headers,
                json={"token": token, "password": "updated-training-password"},
            ).status_code
            == 204
        )
        assert other.get("/api/v1/me").status_code == 401
