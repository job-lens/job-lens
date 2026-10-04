"""Real Resend delivery; no development path that pretends an email was sent."""

import json
import logging
import re
from http.client import HTTPException
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger("job_lens.email")
_TRACE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
# Never log arbitrary provider strings, even if they look like an error code.
# These names are documented at https://resend.com/docs/api-reference/errors.
_PROVIDER_CODES = frozenset(
    {
        "application_error",
        "concurrent_idempotent_requests",
        "daily_quota_exceeded",
        "invalid_attachment",
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


def provider_error_code(error: HTTPError) -> str:
    # Bound reads; do not retain/log response messages, headers, URLs or bodies.
    try:
        with error:
            result = json.loads(error.read(4096))
        name = result.get("name") if isinstance(result, dict) else None
        return name if isinstance(name, str) and name in _PROVIDER_CODES else "unknown"
    except (OSError, ValueError, HTTPException, RecursionError):
        return "unknown"


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
    assert config.mail_api_key is not None
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(
            {"from": config.mail_from, "to": [recipient], "subject": subject, "text": text}
        ).encode(),
        headers={
            "Authorization": "Bearer " + config.mail_api_key.get_secret_value(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    status = None
    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
            result = json.loads(response.read(65536))
            if response.status != 200 or not isinstance(result, dict) or not result.get("id"):
                raise ValueError("delivery not accepted")
    except HTTPError as exc:
        raise delivery_failure(
            "provider_http", trace_id, exc.code, provider_error_code(exc)
        ) from None
    except (URLError, TimeoutError, OSError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        category: Literal["timeout", "transport"] = (
            "timeout" if isinstance(reason, TimeoutError) else "transport"
        )
        raise delivery_failure(category, trace_id, status) from None
    except ValueError:
        raise delivery_failure("protocol", trace_id, status) from None
