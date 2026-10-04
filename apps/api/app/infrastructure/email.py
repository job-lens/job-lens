"""Real Resend delivery; no development path that pretends an email was sent."""

import logging
import re
from threading import Lock
from typing import Literal

import resend
from resend.exceptions import ResendError
from resend.http_client_requests import RequestsClient

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger("job_lens.email")
# The official SDK uses module-global configuration; serialize and restore it.
_SDK_LOCK = Lock()
_SDK_CLIENT = RequestsClient(timeout=10)
_TRACE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
# Never log arbitrary provider strings, even if they look like an error code.
# These names are documented at https://resend.com/docs/api-reference/errors.
_PROVIDER_CODES = frozenset(
    {
        "application_error",
        "concurrent_idempotent_requests",
        "daily_quota_exceeded",
        "invalid_attachment",
        "invalid_api_key",
        "invalid_idempotency_key",
        "invalid_idempotent_request",
        "invalid_parameter",
        "invalid_permission",
        "method_not_allowed",
        "missing_api_key",
        "missing_required_field",
        "missing_required_parameter",
        "monthly_quota_exceeded",
        "not_found",
        "rate_limit_exceeded",
        "resource_locked",
        "restricted_api_key",
        "service_unavailable",
        "suspended_api_key",
        "validation_error",
    }
)


def delivery_failure(
    category: Literal["configuration", "provider_http", "timeout", "transport", "protocol"],
    trace_id: str,
    status: int | None = None,
    provider_code: str = "unknown",
) -> AppError:
    logger.warning(
        "email_delivery_failed category=%s provider_status=%s provider_code=%s trace_id=%s",
        category,
        status if type(status) is int and 100 <= status <= 599 else "unknown",
        provider_code if provider_code in _PROVIDER_CODES else "unknown",
        trace_id if _TRACE_ID.fullmatch(trace_id) else "unknown",
    )
    return AppError(503, "EMAIL_UNAVAILABLE", "邮件服务暂不可用，请稍后再试")


def sdk_transport_category(error: BaseException) -> Literal["timeout", "transport"]:
    # SDK 2.39 wraps Requests errors. Inspect exception types only, never messages.
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(seen) < 8:
        seen.add(id(current))
        kind = type(current)
        if isinstance(current, TimeoutError) or (
            kind.__module__ == "requests.exceptions"
            and kind.__name__ in {"Timeout", "ConnectTimeout", "ReadTimeout"}
        ):
            return "timeout"
        current = current.__cause__ or current.__context__
    return "transport"


def require_delivery(config: Settings, trace_id: str = "unknown") -> None:
    if (
        not config.mail_api_key
        or not config.mail_from
        or any(c in config.mail_from for c in "\r\n")
    ):
        raise delivery_failure("configuration", trace_id)


def send_email(
    config: Settings, recipient: str, subject: str, text: str, trace_id: str = "unknown"
) -> None:
    require_delivery(config, trace_id)
    assert config.mail_api_key is not None and config.mail_from is not None
    try:
        with _SDK_LOCK:
            previous = (resend.api_key, resend.api_url, resend.default_http_client)
            try:
                resend.api_key = config.mail_api_key.get_secret_value()
                # Do not adopt an unrelated RESEND_API_URL/RESEND_API_KEY environment.
                resend.api_url = "https://api.resend.com"
                resend.default_http_client = _SDK_CLIENT
                result = resend.Emails.send(
                    {"from": config.mail_from, "to": [recipient], "subject": subject, "text": text}
                )
            finally:
                resend.api_key, resend.api_url, resend.default_http_client = previous
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("id"), str)
            or not result["id"]
        ):
            raise ValueError("delivery not accepted")
    except ResendError as exc:
        if exc.error_type == "HttpClientError":
            raise delivery_failure(sdk_transport_category(exc), trace_id) from None
        code = exc.code
        status = (
            int(code) if isinstance(code, str) and re.fullmatch(r"[1-5][0-9]{2}", code) else code
        )
        raise delivery_failure(
            "provider_http",
            trace_id,
            status if type(status) is int else None,
            exc.error_type if isinstance(exc.error_type, str) else "unknown",
        ) from None
    except (TimeoutError, OSError) as exc:
        raise delivery_failure(sdk_transport_category(exc), trace_id) from None
    except Exception:
        # SDK exceptions can embed raw provider bodies; never expose them.
        raise delivery_failure("protocol", trace_id) from None
