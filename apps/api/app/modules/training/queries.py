from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import Actor
from app.modules.cases.queries import authorized_case_ids
from app.modules.training.models import TrainingTask


def current_tasks(
    session: Session, actor: Actor, case_ids: list[UUID]
) -> dict[UUID, tuple[UUID, str]]:
    rows = session.scalars(
        select(TrainingTask)
        .where(
            TrainingTask.case_id.in_(case_ids), TrainingTask.case_id.in_(authorized_case_ids(actor))
        )
        .order_by(TrainingTask.created_at.desc(), TrainingTask.id.desc())
    )
    result: dict[UUID, tuple[UUID, str]] = {}
    for task in rows:
        if task.case_id not in result or (
            result[task.case_id][1] in {"completed", "cancelled"}
            and task.status not in {"completed", "cancelled"}
        ):
            result[task.case_id] = (task.id, task.status)
    return result


def workload_counts(session: Session, actor: Actor) -> tuple[int, int]:
    scope = TrainingTask.case_id.in_(authorized_case_ids(actor))
    pending = (
        session.scalar(
            select(func.count())
            .select_from(TrainingTask)
            .where(
                scope,
                TrainingTask.status.in_(
                    ["not_started", "in_progress", "paused", "changes_requested"]
                ),
            )
        )
        or 0
    )
    review = (
        session.scalar(
            select(func.count())
            .select_from(TrainingTask)
            .where(scope, TrainingTask.status == "submitted")
        )
        or 0
    )
    return pending, review
