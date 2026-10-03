"""Manual case grants: administrator capability never implies access to case content."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, forbidden, not_found
from app.core.http import require_version
from app.core.types import Actor
from app.infrastructure.db import utcnow
from app.infrastructure.models import AuditEvent
from app.modules.cases.models import Case, CaseGrant
from app.modules.identity.queries import certified_counselor, require_administrator


def view(s: Session, row: Case) -> dict[str, object]:
    return {
        "id": row.id,
        "learner_id": row.learner_id,
        "version": row.version,
        "counselor_ids": list(
            s.scalars(
                select(CaseGrant.counselor_id)
                .where(CaseGrant.case_id == row.id, CaseGrant.revoked_at.is_(None))
                .order_by(CaseGrant.counselor_id)
            )
        ),
    }


def list_cases(s: Session, actor: Actor, limit: int, offset: int) -> dict[str, object]:
    require_administrator(s, actor)
    rows = s.scalars(select(Case).order_by(Case.id).offset(offset).limit(limit))
    return {
        "items": [view(s, row) for row in rows],
        "total": s.scalar(select(func.count()).select_from(Case)) or 0,
    }


def assign(
    s: Session,
    actor: Actor,
    case_id: UUID,
    counselor_id: UUID,
    assigned: bool,
    version: str,
    trace: str,
) -> dict[str, object]:
    require_administrator(s, actor)
    if counselor_id == actor.user_id:
        raise forbidden()
    eligible = certified_counselor(
        s, counselor_id
    )  # Lock target before case, including revocations.
    row = s.scalar(select(Case).where(Case.id == case_id).with_for_update())
    if row is None:
        raise not_found()
    if row.learner_id in {actor.user_id, counselor_id}:
        raise forbidden()
    require_version(version, row.version)
    if assigned and (not eligible or row.lifecycle == "closed"):
        raise conflict("COUNSELOR_NOT_ELIGIBLE")
    grant = s.get(CaseGrant, (case_id, counselor_id), populate_existing=True)
    if assigned:
        if grant is None:
            s.add(CaseGrant(case_id=case_id, counselor_id=counselor_id))
        else:
            grant.revoked_at = None
    elif grant:
        grant.revoked_at = utcnow()
    row.version += 1
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action="cases.counselor_assigned" if assigned else "cases.counselor_unassigned",
            resource_type="case",
            resource_id=case_id,
            trace_id=trace,
        )
    )
    s.flush()
    return view(s, row)


def revoke_counselor_grants(s: Session, actor: Actor, user_id: UUID, trace: str) -> None:
    require_administrator(s, actor)
    rows = s.scalars(
        select(Case)
        .join(CaseGrant, CaseGrant.case_id == Case.id)
        .where(CaseGrant.counselor_id == user_id, CaseGrant.revoked_at.is_(None))
        .order_by(Case.id)
        .with_for_update(of=Case)
    )
    for row in rows:
        grant = s.get(CaseGrant, (row.id, user_id))
        assert grant is not None
        grant.revoked_at = utcnow()
        row.version += 1
        s.add(
            AuditEvent(
                actor_id=actor.user_id,
                action="cases.certification_grant_revoked",
                resource_type="case",
                resource_id=row.id,
                trace_id=trace,
            )
        )
    s.flush()
