from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
ERRORS: dict[int | str, dict[str, Any]] = {"default": ERROR_RESPONSE, 422: ERROR_RESPONSE}
AUTHENTICATED_ERRORS: dict[int | str, dict[str, Any]] = {
    **ERRORS,
    401: ERROR_RESPONSE,
    403: ERROR_RESPONSE,
    404: ERROR_RESPONSE,
}


class CsrfToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csrf_token: Annotated[str, Field(min_length=16, max_length=256)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login_name: Annotated[str, Field(min_length=1, max_length=80)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class LoginResult(CsrfToken):
    user: User


class PreferencesWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    font_scale: Annotated[float, Field(json_schema_extra={"enum": [1, 1.25, 1.5]})]
    volume: Annotated[float, Field(ge=0, le=1)]
    quiet_mode: bool
    speech_enabled: bool
    vibration_enabled: bool

    @field_validator("font_scale")
    @classmethod
    def supported_scale(cls, value: float) -> float:
        if value not in (1, 1.25, 1.5):
            raise ValueError("unsupported font scale")
        return value


class Preferences(PreferencesWrite):
    version: Annotated[int, Field(ge=1, le=2147483647)]


class ProfileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    sensory_preferences: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=40)]], Field(max_length=10)
    ]
    communication_preference: Annotated[str, Field(max_length=200)]
    work_notes: Annotated[str, Field(max_length=1000)]


class Profile(ProfileWrite):
    user_id: UUID
    version: Annotated[int, Field(ge=1, le=2147483647)]


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    screenshot_annotation: bool
    realtime_calls: bool
    sop_conversion: bool
    realtime_ar: bool
    precise_location: bool


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Annotated[str, Field(min_length=3, max_length=80, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]

    @field_validator("email", mode="before")
    @classmethod
    def canonical_email(cls, value: Any) -> Any:
        return value.strip().casefold() if isinstance(value, str) else value


class RegistrationRequest(EmailRequest):
    code: Annotated[str, Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")]
    password: Annotated[str, Field(min_length=12, max_length=256)]
    display_name: Annotated[str, Field(min_length=1, max_length=80)]


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: Annotated[str, Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")]
    password: Annotated[str, Field(min_length=12, max_length=256)]


class EmailAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: Literal["请求已受理，请查看邮箱。"]
