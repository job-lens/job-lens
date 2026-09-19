from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import not_found
from app.core.types import Actor
from app.modules.cases.models import Case, CaseGrant
from app.modules.cases.public import CaseAccess


def read_access(session: Session, actor: Actor, case_id: UUID) -> CaseAccess:
    # The database predicate is shared by detail and list queries.
    record = session.scalar(select(Case).where(Case.id == case_id, scope_predicate(actor)))
    if record is None:
        raise not_found()
    counselors = session.scalars(
        select(CaseGrant.counselor_id).where(
            CaseGrant.case_id == case_id,
            CaseGrant.revoked_at.is_(None),
        )
    )
    access = CaseAccess(record.id, record.learner_id, frozenset(counselors))
    access.require_read(actor)
    return access


def scope_predicate(actor: Actor) -> ColumnElement[bool]:
    predicate: ColumnElement[bool] = or_(
        (Case.learner_id == actor.user_id) & ("learner" in actor.roles),
        exists(
            select(CaseGrant.case_id).where(
                CaseGrant.case_id == Case.id,
                CaseGrant.counselor_id == actor.user_id,
                CaseGrant.revoked_at.is_(None),
            )
        )
        & ("counselor" in actor.roles),
    )
    return predicate
