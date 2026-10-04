import json
from contextlib import contextmanager
from http.client import IncompleteRead
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest
from app.core.config import Settings
from app.core.errors import AppError
from app.infrastructure.email import require_delivery, send_email


def config():
    return Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        mail_api_key="test-only-key",
        mail_from="Job Lens <test@example.invalid>",
        _env_file=None,
    )


def test_adapter_sends_real_provider_contract_without_logging_secrets(monkeypatch, caplog):
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
    assert not caplog.records


def test_adapter_sanitizes_provider_failures(monkeypatch):
    def transport(*args, **kwargs):
        raise URLError("private address and bearer credential")

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    with pytest.raises(AppError) as failure:
        send_email(config(), "learner@example.invalid", "验证码", "test message")
    assert failure.value.status == 503 and failure.value.code == "EMAIL_UNAVAILABLE"
    assert "private" not in str(failure.value)


def assert_private_values_absent(caplog):
    for value in ("test-only-key", "learner@example.invalid", "private-code", "private-secret"):
        assert value not in caplog.text
    assert len(caplog.records) == 1
    assert caplog.records[0].name == "job_lens.email"
    assert caplog.records[0].exc_info is None


@pytest.mark.parametrize("status", [400, 401, 403, 422, 429, 500, 503])
def test_http_errors_log_only_allowlisted_metadata(monkeypatch, caplog, status):
    calls = []
    body = json.dumps({"name": "validation_error", "message": "private-secret"}).encode()

    def transport(*args, **kwargs):
        calls.append(1)
        raise HTTPError(
            "https://private-secret.invalid", status, "private-secret", {}, BytesIO(body)
        )

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    with pytest.raises(AppError) as failure:
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-1")
    assert failure.value.status == 503 and failure.value.code == "EMAIL_UNAVAILABLE"
    assert failure.value.title == "邮件服务暂不可用，请稍后再试"
    assert calls == [1]
    assert caplog.messages == [
        "email_delivery_failed category=provider_http "
        f"provider_status={status} provider_code=validation_error trace_id=mail-trace-1"
    ]
    assert_private_values_absent(caplog)


@pytest.mark.parametrize(
    "body",
    [
        b'{"name":"private-secret","message":"private-code"}',
        b'{"name":["private-secret"]}',
        b'{"name":{"private-secret":1}}',
        b"[]",
        b"private-secret",
        b"\xff",
        b'{"name":"validation_error","message":"' + b"x" * 4096,
        b"[" * 2000 + b"]" * 2000,
    ],
)
def test_unknown_or_malformed_provider_body_is_never_logged(monkeypatch, caplog, body):
    class BoundedBody(BytesIO):
        def read(self, limit):
            assert limit == 4096
            return super().read(limit)

    def transport(*args, **kwargs):
        raise HTTPError(
            "https://private-secret.invalid", 403, "private-secret", {}, BoundedBody(body)
        )

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    with pytest.raises(AppError):
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-2")
    assert "provider_code=unknown" in caplog.text
    assert_private_values_absent(caplog)


@pytest.mark.parametrize("failure", [OSError("private-secret"), IncompleteRead(b"private-code")])
def test_provider_error_body_read_failure_preserves_original_503(monkeypatch, caplog, failure):
    class BrokenBody(BytesIO):
        def read(self, limit):
            raise failure

    def transport(*args, **kwargs):
        raise HTTPError("https://private-secret.invalid", 403, "private-secret", {}, BrokenBody())

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    with pytest.raises(AppError) as error:
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-3")
    assert error.value.status == 503
    assert "provider_status=403 provider_code=unknown" in caplog.text
    assert_private_values_absent(caplog)


@pytest.mark.parametrize(
    "failure,category",
    [
        (TimeoutError("private-secret"), "timeout"),
        (URLError(TimeoutError("private-secret")), "timeout"),
        (URLError("private-secret"), "transport"),
        (OSError("private-secret"), "transport"),
        (ValueError("private-secret"), "protocol"),
    ],
)
def test_transport_failure_categories_do_not_log_exceptions(monkeypatch, caplog, failure, category):
    def transport(*args, **kwargs):
        raise failure

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    with pytest.raises(AppError):
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-4")
    assert f"category={category} provider_status=unknown" in caplog.text
    assert_private_values_absent(caplog)


def test_malformed_success_response_logs_protocol_status_only(monkeypatch, caplog):
    class Response:
        status = 200

        def read(self, limit):
            return b'{"message":"private-secret"}'

    @contextmanager
    def transport(*args, **kwargs):
        yield Response()

    monkeypatch.setattr("app.infrastructure.email.urlopen", transport)
    with pytest.raises(AppError):
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-5")
    assert "category=protocol provider_status=200 provider_code=unknown" in caplog.text
    assert_private_values_absent(caplog)


def test_missing_config_logs_safe_category_and_sanitizes_trace(caplog):
    settings = config().model_copy(update={"mail_api_key": None})
    with pytest.raises(AppError):
        require_delivery(settings, "private-secret\ninjected log line")
    assert caplog.messages == [
        "email_delivery_failed category=configuration provider_status=unknown "
        "provider_code=unknown trace_id=unknown"
    ]
    assert_private_values_absent(caplog)
