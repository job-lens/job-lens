"""Explicit administrator operations using the existing account/session model."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, forbidden, not_found, unauthenticated
from app.core.http import require_version
from app.core.types import Actor
from app.infrastructure.db import utcnow
from app.infrastructure.models import AuditEvent
from app.modules.identity.models import (
    AdministratorGrant,
    CounselorCertification,
    ManagementEvent,
    Profile,
    User,
    UserRole,
)
from app.modules.identity.queries import require_administrator


def audit(s: Session, actor: Actor, target: UUID, action: str, reason: str, trace: str) -> None:
    s.add(
        ManagementEvent(
            actor_id=actor.user_id, target_id=target, action=action, reason=reason, trace_id=trace
        )
    )
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action=action,
            resource_type="user",
            resource_id=target,
            trace_id=trace,
        )
    )


def certification(s: Session, user_id: UUID) -> dict[str, object]:
    row = s.get(CounselorCertification, user_id)
    return {
        "user_id": user_id,
        "state": row.state if row else "not_submitted",
        "statement": row.statement if row else "",
        "reason": row.reason if row else "",
        "reviewer_id": row.reviewer_id if row else None,
        "reviewed_at": row.reviewed_at if row else None,
        "version": row.version if row else 1,
    }


def submit(s: Session, actor: Actor, statement: str, version: str, trace: str) -> dict[str, object]:
    user = s.scalar(
        select(User)
        .where(User.id == actor.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.active or actor.credential_version != user.credential_version:
        raise unauthenticated()
    row = s.get(CounselorCertification, actor.user_id, populate_existing=True)
    require_version(version, row.version if row else 1)
    if row and row.state in {"pending", "approved"}:
        raise conflict("CERTIFICATION_NOT_EDITABLE")
    if not row:
        row = CounselorCertification(user_id=actor.user_id, version=1)
        s.add(row)
    row.statement, row.state, row.reason = statement, "pending", ""
    row.reviewer_id, row.reviewed_at = None, None
    row.version += 1
    audit(s, actor, actor.user_id, "identity.certification_submitted", "", trace)
    s.flush()
    return certification(s, actor.user_id)


def review(
    s: Session, actor: Actor, user_id: UUID, decision: str, reason: str, version: str, trace: str
) -> dict[str, object]:
    require_administrator(s, actor)
    if user_id == actor.user_id:
        raise forbidden()
    user = s.scalar(select(User).where(User.id == user_id).with_for_update())
    row = s.get(CounselorCertification, user_id, populate_existing=True)
    if user is None or row is None:
        raise not_found()
    require_version(version, row.version)
    if (decision in {"approved", "rejected"} and row.state != "pending") or (
        decision == "revoked" and row.state != "approved"
    ):
        raise conflict("INVALID_CERTIFICATION_TRANSITION")
    if decision == "approved" and not user.active:
        raise conflict("ACCOUNT_INACTIVE")
    row.state, row.reason = decision, reason
    row.reviewer_id, row.reviewed_at = actor.user_id, utcnow()
    row.version += 1
    if decision == "approved" and s.get(UserRole, (user_id, "counselor")) is None:
        s.add(UserRole(user_id=user_id, role="counselor"))
    elif decision == "revoked":
        # Legacy counselor-only accounts retain baseline registration access so they can
        # sign in and reapply; no case grants are restored by this learner role.
        if s.get(UserRole, (user_id, "learner")) is None:
            s.add(UserRole(user_id=user_id, role="learner"))
        s.execute(delete(UserRole).where(UserRole.user_id == user_id, UserRole.role == "counselor"))
    # Existing cookies never acquire newly approved privileges without a fresh login.
    user.credential_version += 1

    audit(s, actor, user_id, "identity.certification_" + decision, reason, trace)
    s.flush()
    return certification(s, user_id)


def user_view(s: Session, user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "display_name": s.scalar(select(Profile.display_name).where(Profile.user_id == user.id))
        or "",
        "active": user.active,
        "roles": list(
            s.scalars(
                select(UserRole.role).where(UserRole.user_id == user.id).order_by(UserRole.role)
            )
        ),
        "version": user.management_version,
    }


def users(s: Session, actor: Actor, limit: int, offset: int) -> dict[str, object]:
    require_administrator(s, actor)
    rows = s.scalars(select(User).order_by(User.id).offset(offset).limit(limit))
    return {
        "items": [user_view(s, row) for row in rows],
        "total": s.scalar(select(func.count()).select_from(User)) or 0,
    }


def set_status(
    s: Session, actor: Actor, user_id: UUID, active: bool, reason: str, version: str, trace: str
) -> dict[str, object]:
    require_administrator(s, actor)
    if user_id == actor.user_id:
        raise forbidden()
    user = s.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise not_found()
    grant = s.get(AdministratorGrant, user_id)
    if grant and grant.revoked_at is None:
        raise forbidden()  # Administrator lifecycle is operator-controlled, never peer-managed.
    require_version(version, user.management_version)
    user.active = active
    user.management_version += 1
    user.credential_version += 1

    audit(
        s,
        actor,
        user_id,
        "identity.account_activated" if active else "identity.account_suspended",
        reason,
        trace,
    )
    s.flush()
    return user_view(s, user)


def queue(
    s: Session, actor: Actor, limit: int, offset: int, state: str | None
) -> dict[str, object]:
    require_administrator(s, actor)
    query = select(CounselorCertification)
    count = select(func.count()).select_from(CounselorCertification)
    if state:
        query = query.where(CounselorCertification.state == state)
        count = count.where(CounselorCertification.state == state)
    rows = s.scalars(query.order_by(CounselorCertification.user_id).offset(offset).limit(limit))
    return {"items": [certification(s, row.user_id) for row in rows], "total": s.scalar(count) or 0}


def events(s: Session, actor: Actor, limit: int, offset: int) -> list[ManagementEvent]:
    require_administrator(s, actor)
    return list(
        s.scalars(
            select(ManagementEvent)
            .order_by(ManagementEvent.created_at.desc(), ManagementEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
