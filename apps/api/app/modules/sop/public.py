from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PublishedSop:
    revision_id: UUID
    case_id: UUID
    step_ids: tuple[UUID, ...]
