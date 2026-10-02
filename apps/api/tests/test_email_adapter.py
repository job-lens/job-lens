import json
from contextlib import contextmanager
from urllib.error import URLError

import pytest
from app.core.config import Settings
from app.core.errors import AppError
from app.infrastructure.email import send_email


def config():
    return Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        mail_api_key="test-only-key",
        mail_from="Job Lens <test@example.invalid>",
        _env_file=None,
    )


def test_adapter_sends_real_provider_contract_without_logging_secrets(monkeypatch):
    class Response:
        status = 200

        def read(self, limit):
            assert limit == 65536
            return b'{"id":"mail-id"}'

    @contextmanager
    def transport(request, timeout):
        assert request.full_url == "https://api.resend.com/emails"
        assert request.method == "POST" and timeout == 10
        assert request.get_header("Authorization") == "Bearer test-only-key"
        assert json.loads(request.data) == {
            "from": "Job Lens <test@example.invalid>",
            "to": ["learner@example.invalid"],
            "subject": "验证码",
            "text": "test message",
        }
        yield Response()

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    send_email(config(), "learner@example.invalid", "验证码", "test message")


def test_adapter_sanitizes_provider_failures(monkeypatch):
    def transport(*args, **kwargs):
        raise URLError("private address and bearer credential")

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    with pytest.raises(AppError) as failure:
        send_email(config(), "learner@example.invalid", "验证码", "test message")
    assert failure.value.status == 503 and failure.value.code == "EMAIL_UNAVAILABLE"
    assert "private" not in str(failure.value)
