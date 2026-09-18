from dataclasses import dataclass
from typing import Literal
from uuid import UUID

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type Role = Literal["learner", "counselor"]


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    roles: frozenset[Role]
