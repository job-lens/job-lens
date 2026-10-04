import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
import requests
import resend
from app.core.config import Settings
from app.core.errors import AppError
from app.infrastructure.email import require_delivery, send_email
from resend.exceptions import ResendError


def config(key="test-only-key"):
    return Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        mail_api_key=key,
        mail_from="JobLens <sender@example.invalid>",
        _env_file=None,
    )


def response(status=200, body=None, content_type="application/json"):
    return Mock(
        content=json.dumps(body or {"id": "test-message-id"}).encode(),
        status_code=status,
        headers={"Content-Type": content_type, "private-header": "private-secret"},
    )


def assert_private_values_absent(caplog):
    for value in ("test-only-key", "learner@example.invalid", "private-code", "private-secret"):
        assert value not in caplog.text
    assert len(caplog.records) == 1
    assert caplog.records[0].name == "job_lens.email"
    assert caplog.records[0].exc_info is None


def test_official_sdk_uses_qunxue_transport_headers_without_logging_secrets(monkeypatch, caplog):
    calls = []
    monkeypatch.setattr(resend, "api_url", "https://unrelated.example.invalid")
    monkeypatch.setattr(resend, "api_key", "unrelated-private-key")
    original = (resend.api_key, resend.api_url, resend.default_http_client)

    def transport(**kwargs):
        calls.append(kwargs)
        return response()

    monkeypatch.setattr("resend.http_client_requests.requests.request", transport)
    send_email(config(), "learner@example.invalid", "验证码", "private-code", "sdk-success")
    assert len(calls) == 1
    call = calls[0]
    assert call["method"] == "post" and call["url"] == "https://api.resend.com/emails"
    assert call["headers"] == {
        "Authorization": "Bearer test-only-key",
        "User-Agent": "resend-python:2.39.0",
        "Accept": "application/json",
    }
    assert call["json"] == {
        "from": "JobLens <sender@example.invalid>",
        "to": ["learner@example.invalid"],
        "subject": "验证码",
        "text": "private-code",
    }
    assert call["timeout"] == 10
    assert not caplog.records
    assert (resend.api_key, resend.api_url, resend.default_http_client) == original


@pytest.mark.parametrize("status", [400, 401, 403, 422, 429, 500, 503])
def test_sdk_http_errors_log_only_allowlisted_metadata_no_retry(monkeypatch, caplog, status):
    transport = Mock(
        return_value=response(
            status,
            {
                "name": "validation_error",
                "message": "private-secret",
            },
        )
    )
    monkeypatch.setattr("resend.http_client_requests.requests.request", transport)
    with pytest.raises(AppError) as failure:
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-1")
    assert failure.value.status == 503 and failure.value.code == "EMAIL_UNAVAILABLE"
    assert failure.value.title == "邮件服务暂不可用，请稍后再试"
    assert transport.call_count == 1
    assert caplog.messages == [
        "email_delivery_failed category=provider_http "
        f"provider_status={status} provider_code=validation_error trace_id=mail-trace-1"
    ]
    assert_private_values_absent(caplog)


@pytest.mark.parametrize("code", [403, "403", "private-secret", True, None, 999])
def test_sdk_error_status_is_sanitized_and_global_configuration_restored(monkeypatch, caplog, code):
    original = (resend.api_key, resend.api_url, resend.default_http_client)
    failure = ResendError(
        code=code,
        error_type="private-secret",
        message="private-secret",
        suggested_action="private-secret",
        headers={"secret": "private-secret"},
    )
    send = Mock(side_effect=failure)
    monkeypatch.setattr("resend.Emails.send", send)
    with pytest.raises(AppError):
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-2")
    assert send.call_count == 1
    expected = "403" if code in (403, "403") else "unknown"
    assert f"provider_status={expected}" in caplog.text
    assert "provider_code=unknown" in caplog.text
    assert (resend.api_key, resend.api_url, resend.default_http_client) == original
    assert_private_values_absent(caplog)


@pytest.mark.parametrize(
    "failure,category",
    [
        (requests.exceptions.Timeout("private-secret"), "timeout"),
        (requests.exceptions.ConnectTimeout("private-secret"), "timeout"),
        (requests.exceptions.ReadTimeout("private-secret"), "timeout"),
        (requests.exceptions.ConnectionError("private-secret"), "transport"),
        (requests.exceptions.SSLError("private-secret"), "transport"),
    ],
)
def test_real_sdk_wrapped_transport_errors_keep_safe_category(
    monkeypatch, caplog, failure, category
):
    transport = Mock(side_effect=failure)
    monkeypatch.setattr("resend.http_client_requests.requests.request", transport)
    with pytest.raises(AppError) as error:
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-3")
    assert error.value.status == 503
    assert transport.call_count == 1
    assert f"category={category} provider_status=unknown" in caplog.text
    assert_private_values_absent(caplog)


@pytest.mark.parametrize(
    "status,content_type,body",
    [
        (403, "text/html", b"<html>private-secret</html>"),
        (403, "application/json", b"private-secret"),
        (503, "text/plain", b"private-secret"),
    ],
)
def test_sdk_non_json_failures_do_not_expose_provider_body(
    monkeypatch, caplog, status, content_type, body
):
    resp = response(status, content_type=content_type)
    resp.content = body
    transport = Mock(return_value=resp)
    monkeypatch.setattr("resend.http_client_requests.requests.request", transport)
    with pytest.raises(AppError):
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-4")
    assert transport.call_count == 1
    assert f"provider_status={status} provider_code=application_error" in caplog.text
    assert_private_values_absent(caplog)


@pytest.mark.parametrize(
    "result", [None, [], {}, {"id": ""}, {"id": 1}, {"message": "private-secret"}]
)
def test_sdk_response_requires_nonempty_message_id(monkeypatch, caplog, result):
    send = Mock(return_value=result)
    monkeypatch.setattr("resend.Emails.send", send)
    with pytest.raises(AppError):
        send_email(config(), "learner@example.invalid", "验证码", "private-code", "mail-trace-5")
    assert send.call_count == 1
    assert "category=protocol provider_status=unknown" in caplog.text
    assert_private_values_absent(caplog)


def test_missing_config_logs_safe_category_and_sanitizes_trace(monkeypatch, caplog):
    send = Mock()
    monkeypatch.setattr("resend.Emails.send", send)
    settings = config().model_copy(update={"mail_api_key": None})
    with pytest.raises(AppError):
        require_delivery(settings, "private-secret\ninjected log line")
    assert caplog.messages == [
        "email_delivery_failed category=configuration provider_status=unknown "
        "provider_code=unknown trace_id=unknown"
    ]
    send.assert_not_called()
    assert_private_values_absent(caplog)


def test_parallel_sends_do_not_mix_sdk_credentials(monkeypatch):
    captured = []

    def send(params):
        captured.append((resend.api_key, params["to"][0]))
        return {"id": "test-message-id"}

    monkeypatch.setattr("resend.Emails.send", send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(send_email, config(f"key-{i}"), f"user-{i}@example.invalid", "test", "test")
            for i in range(10)
        ]
        for future in futures:
            future.result()
    assert sorted(captured) == [(f"key-{i}", f"user-{i}@example.invalid") for i in range(10)]


def test_settings_keep_joblens_specific_env_mapping(monkeypatch):
    monkeypatch.setenv("JOB_LENS_MAIL_API_KEY", "joblens-test-key")
    monkeypatch.setenv("JOB_LENS_MAIL_FROM", "JobLens <joblens@example.invalid>")
    monkeypatch.setenv("QUNXUE_RESEND_API_KEY", "unrelated-test-key")
    monkeypatch.setenv("QUNXUE_EMAIL_FROM", "unrelated@example.invalid")
    settings = Settings(database_url="postgresql+psycopg://unused@localhost/unused", _env_file=None)
    assert settings.mail_api_key.get_secret_value() == "joblens-test-key"
    assert settings.mail_from == "JobLens <joblens@example.invalid>"
