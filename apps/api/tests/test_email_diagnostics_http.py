"""Trace correlation through real routing, with isolated DB and mail transports."""

import re
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


class DatabaseStub:
    @contextmanager
    def transaction(self):
        session = MagicMock()
        session.scalar.return_value = None
        yield session


@pytest.mark.parametrize("path", ["registration-code", "password-reset-requests"])
@pytest.mark.parametrize("configured", [True, False])
@pytest.mark.parametrize("trace", ["mail-http-trace", "invalid trace"])
def test_delivery_warning_matches_public_response_trace(
    monkeypatch, caplog, path, configured, trace
):
    settings = Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        trusted_hosts=["testserver"],
        mail_api_key="private-key" if configured else None,
        mail_from="sender@example.invalid" if configured else None,
        _env_file=None,
    )
    monkeypatch.setattr("app.web.registration.check", lambda *args: None)
    monkeypatch.setattr("app.modules.identity.registration.email_budget", lambda *args: None)
    monkeypatch.setattr("app.modules.identity.registration.hash_password", lambda *args: "digest")
    calls = []

    def transport(*args, **kwargs):
        calls.append(1)
        raise HTTPError(
            "https://api.resend.com/emails",
            403,
            "private-provider-message",
            {},
            BytesIO(b'{"name":"validation_error","message":"private-provider-message"}'),
        )

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    with TestClient(create_app(settings, DatabaseStub())) as client:
        result = client.post(
            f"/api/v1/auth/{path}",
            headers={"X-CSRF-Token": "test-only-csrf-token", "X-Request-ID": trace},
            json={"email": "learner@example.invalid"},
        )
    assert result.status_code == 503
    assert result.json()["code"] == "EMAIL_UNAVAILABLE"
    assert result.json()["title"] == "邮件服务暂不可用，请稍后再试"
    response_trace = result.headers["x-request-id"]
    assert response_trace == result.json()["trace_id"]
    assert (
        response_trace == trace
        if trace == "mail-http-trace"
        else re.fullmatch(r"[0-9a-f]{32}", response_trace)
    )
    assert len(caplog.records) == 1
    assert f"trace_id={response_trace}" in caplog.messages[0]
    assert ("category=provider_http" if configured else "category=configuration") in caplog.text
    assert calls == ([1] if configured else [])
    for value in ("private-key", "private-provider-message", "learner@example.invalid"):
        assert value not in caplog.text
        assert value not in result.text
