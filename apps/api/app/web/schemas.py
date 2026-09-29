from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import Role


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    title: str
    status: int
    code: str
    trace_id: str


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    # The contract declares uniqueItems; a list keeps the response order stable for clients.
    roles: Annotated[
        list[Role], Field(min_length=1, max_length=2, json_schema_extra={"uniqueItems": True})
    ]


ERROR_RESPONSE: dict[str, Any] = {
    "description": "Structured failure",
    "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
}
# Every operation declares the shared failure shape; specific codes are added per route.
ERRORS: dict[int | str, dict[str, Any]] = {"default": ERROR_RESPONSE}
AUTHENTICATED_ERRORS: dict[int | str, dict[str, Any]] = {
    **ERRORS,
    401: ERROR_RESPONSE,
    403: ERROR_RESPONSE,
    404: ERROR_RESPONSE,
}
