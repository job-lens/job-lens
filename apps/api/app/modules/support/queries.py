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
