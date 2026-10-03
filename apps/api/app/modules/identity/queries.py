from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import not_found, unauthenticated
from app.core.security import SessionWindow, token_digest
from app.core.types import Actor, Role
from app.modules.identity.models import Profile, SessionRecord, User, UserRole
from app.modules.identity.public import UserView

_ROLES = frozenset({"learner", "counselor"})


def resolve_actor(session: Session, token: str, now: datetime) -> Actor:
    """Turn an opaque session token into an actor, or reject it. Never reports why."""
    record = session.scalar(
        select(SessionRecord).where(SessionRecord.token_hash == token_digest(token))
    )
    if record is None or record.user_id is None:
        raise unauthenticated()
    # State, credential generation and roles must come from one SQL snapshot. Otherwise
    # approval between separate reads could lend new roles to a pre-approval cookie.
    rows = session.execute(
        select(User, UserRole.role)
        .outerjoin(UserRole, UserRole.user_id == User.id)
        .where(User.id == record.user_id)
        .execution_options(populate_existing=True)
    ).all()
    user = rows[0][0] if rows else None
    if user is None or not user.active or user.credential_version != record.credential_version:
        raise unauthenticated()
    window = SessionWindow(record.created_at, record.last_seen_at, record.revoked_at is not None)
    if not window.valid_at(now) or record.expires_at <= now:
        raise unauthenticated()
    granted = (row[1] for row in rows)
    # A role row outside the contract's enum is ignored rather than trusted.
    roles = frozenset(cast(Role, role) for role in granted if role in _ROLES)
    if not roles:
        raise unauthenticated()
    return Actor(record.user_id, roles, user.credential_version)


def load_user(session: Session, actor: Actor) -> UserView:
    display_name = session.scalar(
        select(Profile.display_name).where(Profile.user_id == actor.user_id)
    )
    if display_name is None:
        raise not_found()
    return UserView(actor.user_id, display_name, tuple(sorted(actor.roles)))


def profile_snapshot(session: Session, user_id: UUID) -> dict[str, object]:
    from app.modules.identity.models import Preferences

    profile = session.get(Profile, user_id)
    preferences = session.get(Preferences, user_id)
    if profile is None or preferences is None:
        raise not_found()
    return {
        "user_id": user_id,
        "display_name": profile.display_name,
        "sensory_preferences": profile.sensory_preferences,
        "communication_preference": profile.communication_preference,
        "work_notes": profile.work_notes,
        "version": profile.version,
        "preferences": {
            "font_scale": preferences.font_scale,
            "volume": preferences.volume,
            "quiet_mode": preferences.quiet_mode,
            "speech_enabled": preferences.speech_enabled,
            "vibration_enabled": preferences.vibration_enabled,
            "version": preferences.version,
        },
    }


def is_administrator(session: Session, actor: Actor, *, lock: bool = False) -> bool:
    from app.modules.identity.models import AdministratorGrant

    query = select(User).where(User.id == actor.user_id).execution_options(populate_existing=True)
    user = session.scalar(query.with_for_update() if lock else query)
    grant = session.get(AdministratorGrant, actor.user_id, populate_existing=True)
    return bool(
        user
        and user.active
        and actor.credential_version == user.credential_version
        and grant
        and grant.revoked_at is None
    )


def require_administrator(session: Session, actor: Actor) -> None:
    from app.core.errors import forbidden

    # Low-volume administrative transactions share operator lock ordering. This avoids
    # two administrators reviewing each other locking actor/target in opposite order.
    session.execute(text("SELECT pg_advisory_xact_lock(72631841)"))
    if not is_administrator(session, actor, lock=True):
        raise forbidden()


def certified_counselor(session: Session, user_id: UUID) -> bool:
    from app.modules.identity.models import CounselorCertification

    user = session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise not_found()
    certification = session.get(CounselorCertification, user_id, populate_existing=True)
    role = session.get(UserRole, (user_id, "counselor"))
    return bool(
        user and user.active and certification and certification.state == "approved" and role
    )
