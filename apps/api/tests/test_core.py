from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import Settings
from app.core.errors import AppError
from app.core.http import require_idempotency_key, require_version
from app.core.security import (
    SessionWindow,
    hash_password,
    new_token,
    token_digest,
    verify_csrf,
    verify_password,
)


@pytest.mark.parametrize(
    "header,status", [(None, 428), ('W/"1"', 400), ("*", 400), ('"0"', 400), ('"2"', 412)]
)
def test_version_rejections(header, status):
    with pytest.raises(AppError) as exc:
        require_version(header, 1)
    assert exc.value.status == status


def test_version_success():
    require_version('"7"', 7)


@pytest.mark.parametrize("key", [None, "short", "x " * 20, "x" * 129, "x" * 15 + "\n"])
def test_key_rejections(key):
    with pytest.raises(AppError):
        require_idempotency_key(key)


def test_token_and_password_primitives():
    token = new_token()
    assert len(token) >= 43 and token != new_token()
    assert token not in token_digest(token)
    digest = hash_password("architecture-test-password")
    assert verify_password("architecture-test-password", digest)
    assert not verify_password("wrong", digest)
    assert not verify_password("password", "invalid-hash")


@pytest.mark.parametrize(
    "origin,token",
    [(None, "value"), ("https://evil.invalid", "value"), ("https://jl.invalid", None)],
)
def test_csrf_rejections(origin, token):
    with pytest.raises(AppError):
        verify_csrf(origin, "https://jl.invalid", token, token_digest("value"))


def test_csrf_success_and_mismatch():
    token = new_token()
    verify_csrf("https://jl.invalid", "https://jl.invalid", token, token_digest(token))
    with pytest.raises(AppError):
        verify_csrf("https://jl.invalid", "https://jl.invalid", new_token(), token_digest(token))


def test_session_windows():
    now = datetime.now(UTC)
    assert SessionWindow(now, now).valid_at(now)
    assert not SessionWindow(now, now, revoked=True).valid_at(now)
    assert not SessionWindow(now - timedelta(hours=12), now).valid_at(now)
    assert not SessionWindow(now - timedelta(hours=3), now - timedelta(hours=2)).valid_at(now)
    assert not SessionWindow(now, now + timedelta(seconds=1)).valid_at(now)


def test_configuration_is_explicit_and_secret_repr_is_redacted():
    url = "postgresql+psycopg://test:secret-in-config@localhost/job_lens_test"
    settings = Settings(database_url=url, _env_file=None)
    assert "secret-in-config" not in repr(settings)
    with pytest.raises(ValueError):
        Settings(database_url=url, environment="production", _env_file=None)
    with pytest.raises(ValueError):
        Settings(database_url=url, trusted_hosts=["*"], _env_file=None)
    with pytest.raises(ValueError):
        Settings(database_url="sqlite://", _env_file=None)
