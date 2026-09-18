from dataclasses import dataclass
from uuid import UUID

from app.core.errors import forbidden, not_found
from app.core.types import Actor


@dataclass(frozen=True)
class CaseAccess:
    case_id: UUID
    learner_id: UUID
    counselor_ids: frozenset[UUID]

    def require_read(self, actor: Actor) -> None:
        learner = "learner" in actor.roles and actor.user_id == self.learner_id
        counselor = "counselor" in actor.roles and actor.user_id in self.counselor_ids
        if not (learner or counselor):
            raise not_found()

    def require_counselor(self, actor: Actor) -> None:
        self.require_read(actor)
        if "counselor" not in actor.roles or actor.user_id not in self.counselor_ids:
            raise forbidden()

    def require_learner(self, actor: Actor) -> None:
        self.require_read(actor)
        if "learner" not in actor.roles or actor.user_id != self.learner_id:
            raise forbidden()
