from collections.abc import Callable
from typing import Annotated, cast

from fastapi import Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, WithJsonSchema
from sqlalchemy.orm import Session

from app.core.types import Actor, JsonObject, JsonValue
from app.infrastructure.idempotency import CommandResult, Scope, execute_once, fingerprint
from app.web.identity import ETAG, write_check
from app.web.schemas import AUTHENTICATED_ERRORS, ERROR_RESPONSE

Idempotency = Annotated[
    str, Header(alias="Idempotency-Key", min_length=16, max_length=128, pattern=r"^[!-~]+$")
]
Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[
    str | None, Query(max_length=512), WithJsonSchema({"type": "string", "maxLength": 512})
]
READ_RESPONSES = {**AUTHENTICATED_ERRORS, 200: {"headers": {"ETag": ETAG}}}
WRITE_RESPONSES = {**READ_RESPONSES, 412: ERROR_RESPONSE, 428: ERROR_RESPONSE}


def command(
    request: Request,
    s: Session,
    actor: Actor,
    csrf: str,
    key: str,
    body: JsonObject,
    version: str | None,
    authorize: Callable[[], None],
    apply: Callable[[], BaseModel],
    *,
    status: int = 200,
    etag: str | None = None,
) -> JSONResponse:
    write_check(request, s, csrf)

    def run() -> CommandResult:
        result = apply()
        headers = {"ETag": f'"{getattr(result, etag)}"'} if etag else {}
        return CommandResult(status, cast(JsonValue, result.model_dump(mode="json")), headers)

    result = execute_once(
        s,
        Scope(actor.user_id, request.method, request.url.path, key),
        fingerprint(body, version),
        authorize,
        run,
    )
    return JSONResponse(result.body, status_code=result.status, headers=result.headers)
