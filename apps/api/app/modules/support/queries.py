from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import Actor
from app.modules.cases.queries import authorized_case_ids
from app.modules.support.models import Assistance


def pending_count(session: Session, actor: Actor) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(Assistance)
            .where(
                Assistance.case_id.in_(authorized_case_ids(actor)),
                Assistance.state.in_(["queued", "accepted"]),
            )
        )
        or 0
    )


def request_counts(session: Session, actor: Actor, task_ids: list[UUID]) -> dict[UUID, int]:
    rows = session.execute(
        select(Assistance.task_id, func.count())
        .where(Assistance.case_id.in_(authorized_case_ids(actor)), Assistance.task_id.in_(task_ids))
        .group_by(Assistance.task_id)
    )
    return {task_id: count for task_id, count in rows if task_id is not None}
