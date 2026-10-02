import base64
import binascii
import hashlib
import json
from datetime import datetime
from uuid import UUID

from app.core.errors import AppError


def cursor_scope(actor_id: UUID, kind: str, filters: str = "") -> str:
    return hashlib.sha256(f"{actor_id}:{kind}:{filters}".encode()).hexdigest()[:24]


def decode_cursor(value: str | None, scope: str) -> tuple[datetime, UUID] | None:
    if value is None:
        return None
    try:
        raw = json.loads(
            base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        )
        if not isinstance(raw, dict) or set(raw) != {"s", "t", "i"} or raw["s"] != scope:
            raise ValueError("invalid cursor scope")
        timestamp = datetime.fromisoformat(raw["t"])
        if timestamp.tzinfo is None:
            raise ValueError("naive cursor")
        return timestamp, UUID(raw["i"])
    except (ValueError, TypeError, KeyError, binascii.Error):
        raise AppError(400, "INVALID_CURSOR", "列表位置已失效，请从第一页重新查看") from None


def encode_cursor(timestamp: datetime, identifier: UUID, scope: str) -> str:
    body = json.dumps(
        {"s": scope, "t": timestamp.isoformat(), "i": str(identifier)}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(body).decode().rstrip("=")
