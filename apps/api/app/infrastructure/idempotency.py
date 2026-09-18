import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import conflict
from app.core.http import require_idempotency_key
from app.core.types import JsonObject, JsonValue
from app.infrastructure.db import utcnow
from app.infrastructure.models import IdempotencyRecord


@dataclass(frozen=True)
class Scope:
    actor_id: UUID
    method: str
    path: str
    key: str


@dataclass(frozen=True)
class CommandResult:
    status: int
    body: JsonValue
    headers: dict[str, str]


def fingerprint(body: JsonObject, version: str | None = None) -> str:
    data = json.dumps(
        {"body": body, "version": version}, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(data.encode()).hexdigest()


def execute_once(
    session: Session,
    scope: Scope,
    request_fingerprint: str,
    authorize: Callable[[], None],
    command: Callable[[], CommandResult],
) -> CommandResult:
    """Caller owns the transaction; replay reauthorizes before reading a stored result."""
    authorize()
    require_idempotency_key(scope.key)
    values = dict(actor_id=scope.actor_id, method=scope.method, path=scope.path, key=scope.key)
    session.execute(
        insert(IdempotencyRecord)
        .values(
            **values,
            id=uuid4(),
            created_at=utcnow(),
            fingerprint=request_fingerprint,
            response_headers={},
            expires_at=utcnow() + timedelta(hours=24),
        )
        .on_conflict_do_nothing(constraint="uq_idempotency_scope")
    )
    record = session.scalar(select(IdempotencyRecord).filter_by(**values).with_for_update())
    if record is None:
        raise RuntimeError("idempotency record missing inside transaction")
    if record.fingerprint != request_fingerprint:
        raise conflict("IDEMPOTENCY_CONFLICT")
    if record.response_status is not None:
        return CommandResult(record.response_status, record.response_body, record.response_headers)
    # The command performs If-Match validation after replay detection.
    result = command()
    if not 200 <= result.status < 300:
        raise ValueError("only successful commands can be persisted")
    allowed_headers = {k: v for k, v in result.headers.items() if k.lower() in {"etag", "location"}}
    record.response_status = result.status
    record.response_body = result.body
    record.response_headers = allowed_headers
    session.flush()
    return CommandResult(result.status, result.body, allowed_headers)
