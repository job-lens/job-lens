"""Real Resend delivery; no development path that pretends an email was sent."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.core.errors import AppError


def require_delivery(config: Settings) -> None:
    if (
        not config.mail_api_key
        or not config.mail_from
        or any(c in config.mail_from for c in "\r\n")
    ):
        raise AppError(503, "EMAIL_UNAVAILABLE", "邮件服务暂不可用，请稍后再试")


def send_email(config: Settings, recipient: str, subject: str, text: str) -> None:
    require_delivery(config)
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
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read(65536))
            if response.status != 200 or not isinstance(result, dict) or not result.get("id"):
                raise ValueError("delivery not accepted")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        # Never include the provider response, recipient or token in logs/errors.
        raise AppError(503, "EMAIL_UNAVAILABLE", "邮件服务暂不可用，请稍后再试") from None
