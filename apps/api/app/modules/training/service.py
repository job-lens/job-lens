from datetime import date
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import conflict
from app.core.types import Actor, JsonObject
from app.infrastructure.models import AuditEvent
from app.infrastructure.notifications import append_notifications
from app.modules.cases.queries import read_access
from app.modules.sop.queries import published_snapshot
from app.modules.training.models import StepProgress, TrainingTask


def create_for_publication(
    s: Session, actor: Actor, revision_id: UUID, due_on: date | None, trace_id: str
) -> TrainingTask:
    snapshot = published_snapshot(s, actor, revision_id)
    access = read_access(s, actor, snapshot.case_id, lock=True)
    access.require_counselor(actor)
    if s.scalar(
        select(TrainingTask.id).where(
            TrainingTask.case_id == snapshot.case_id,
            TrainingTask.status.not_in(["completed", "cancelled"]),
        )
    ):
        raise conflict("ACTIVE_TASK_EXISTS")
    task = TrainingTask(case_id=snapshot.case_id, revision_id=revision_id, due_on=due_on)
    s.add(task)
    s.flush()
    for step in cast(list[JsonObject], snapshot.content["steps"]):
        s.add(StepProgress(task_id=task.id, step_id=UUID(str(step["id"])), revision_id=revision_id))
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action="training.created",
            resource_type="task",
            resource_id=task.id,
            trace_id=trace_id,
        )
    )
    append_notifications(s, {access.learner_id}, "training.created", "task", task.id)
    s.flush()
    return task
