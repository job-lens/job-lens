from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found, unauthenticated
from app.core.security import SessionWindow, token_digest
from app.core.types import Actor, Role
from app.modules.identity.models import Profile, SessionRecord, UserRole
from app.modules.identity.public import UserView

_ROLES = frozenset({"learner", "counselor"})


def resolve_actor(session: Session, token: str, now: datetime) -> Actor:
    """Turn an opaque session token into an actor, or reject it. Never reports why."""
    record = session.scalar(
        select(SessionRecord).where(SessionRecord.token_hash == token_digest(token))
    )
    if record is None or record.user_id is None:
        raise unauthenticated()
    window = SessionWindow(record.created_at, record.last_seen_at, record.revoked_at is not None)
    if not window.valid_at(now) or record.expires_at <= now:
        raise unauthenticated()
    granted = session.scalars(select(UserRole.role).where(UserRole.user_id == record.user_id))
    # A role row outside the contract's enum is ignored rather than trusted.
    roles = frozenset(cast(Role, role) for role in granted if role in _ROLES)
    if not roles:
        raise unauthenticated()
    return Actor(record.user_id, roles)


def load_user(session: Session, actor: Actor) -> UserView:
    display_name = session.scalar(
        select(Profile.display_name).where(Profile.user_id == actor.user_id)
    )
    if display_name is None:
        raise not_found()
    return UserView(actor.user_id, display_name, tuple(sorted(actor.roles)))
