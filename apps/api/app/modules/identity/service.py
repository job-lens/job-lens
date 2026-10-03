"""Cookie session lifecycle, adapted to Job Lens' existing transaction boundaries.

Qunxue's opaque-token/digest, active-account and revoke-on-logout design is reused;
no reference database, secrets, configuration or administrator grants are copied.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found, unauthenticated
from app.core.http import require_version
from app.core.security import (
    SessionWindow,
    hash_password,
    new_token,
    token_digest,
    verify_csrf,
    verify_password,
)
from app.core.types import Actor
from app.infrastructure.models import AuditEvent
from app.modules.identity.models import AuthLimit, Preferences, Profile, SessionRecord, User
from app.modules.identity.public import UserView
from app.modules.identity.queries import load_user, resolve_actor

_DUMMY_HASH = hash_password(new_token())


@dataclass(frozen=True)
class SessionGrant:
    token: str | None
    csrf_token: str
    user: UserView | None = None


def session_record(s: Session, token: str | None, now: datetime) -> SessionRecord:
    if not token or len(token) > 256:
        raise unauthenticated()
    record = s.scalar(
        select(SessionRecord)
        .where(SessionRecord.token_hash == token_digest(token))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        record is None
        or record.expires_at <= now
        or not SessionWindow(
            record.created_at, record.last_seen_at, record.revoked_at is not None
        ).valid_at(now)
    ):
        raise unauthenticated()
    return record


def issue_session(s: Session, user_id: UUID | None, now: datetime) -> SessionGrant:
    token, csrf = new_token(), new_token()
    s.add(
        SessionRecord(
            user_id=user_id,
            created_at=now,
            token_hash=token_digest(token),
            csrf_hash=token_digest(csrf),
            last_seen_at=now,
            expires_at=now + timedelta(hours=12) if user_id else now + timedelta(minutes=15),
        )
    )
    s.flush()
    return SessionGrant(token, csrf)


def csrf_grant(s: Session, token: str | None, now: datetime) -> SessionGrant:
    try:
        record = session_record(s, token, now)
        if record.user_id is not None:
            resolve_actor(s, token or "", now)
    except AppError:
        return issue_session(s, None, now)
    csrf = new_token()
    record.csrf_hash = token_digest(csrf)
    return SessionGrant(None, csrf)


def check_write(
    s: Session,
    token: str | None,
    origin: str | None,
    expected_origin: str,
    csrf: str,
    now: datetime,
) -> SessionRecord:
    record = session_record(s, token, now)
    verify_csrf(origin, expected_origin, csrf, record.csrf_hash)
    return record


def login(
    s: Session,
    token: str | None,
    origin: str | None,
    expected_origin: str,
    csrf: str,
    login_name: str,
    password: str,
    now: datetime,
    trace_id: str,
    client_key: str,
) -> SessionGrant:
    old = check_write(s, token, origin, expected_origin, csrf, now)
    take_budget(s, "login-client:" + client_key, 30, timedelta(minutes=15), now)
    take_budget(s, "login-name:" + login_name.strip(), 10, timedelta(minutes=15), now)
    user = s.scalar(select(User).where(User.login_name == login_name.strip()))
    valid = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    if not valid or user is None or not user.active:
        raise AppError(401, "INVALID_CREDENTIALS", "账号或密码不正确")
    try:
        # An incomplete account must not leave a new session behind; login budgets
        # remain outside this savepoint and still commit when authentication fails.
        with s.begin_nested():
            old.revoked_at = now
            grant = issue_session(s, user.id, now)
            actor = resolve_actor(s, grant.token or "", now)
            view = load_user(s, actor)
            s.add(
                AuditEvent(
                    actor_id=user.id,
                    action="identity.login",
                    resource_type="user",
                    resource_id=user.id,
                    trace_id=trace_id,
                )
            )
    except AppError as exc:
        raise AppError(401, "INVALID_CREDENTIALS", "账号或密码不正确") from exc
    return SessionGrant(grant.token, grant.csrf_token, view)


def logout(
    s: Session,
    actor: Actor,
    token: str | None,
    origin: str | None,
    expected_origin: str,
    csrf: str,
    now: datetime,
    trace_id: str,
) -> None:
    record = check_write(s, token, origin, expected_origin, csrf, now)
    if record.user_id != actor.user_id:
        raise unauthenticated()
    record.revoked_at = now
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action="identity.logout",
            resource_type="user",
            resource_id=actor.user_id,
            trace_id=trace_id,
        )
    )


def get_preferences(s: Session, actor: Actor) -> Preferences:
    value = s.get(Preferences, actor.user_id)
    if value is None:
        raise not_found()
    return value


def get_profile(s: Session, actor: Actor) -> Profile:
    value = s.get(Profile, actor.user_id)
    if value is None:
        raise not_found()
    return value


def save_personal(
    s: Session, actor: Actor, kind: str, values: dict[str, object], version: str, trace_id: str
) -> Preferences | Profile:
    record: Preferences | Profile | None
    if kind == "preferences":
        record = s.scalar(
            select(Preferences).where(Preferences.user_id == actor.user_id).with_for_update()
        )
    else:
        record = s.scalar(select(Profile).where(Profile.user_id == actor.user_id).with_for_update())
    if record is None:
        raise not_found()
    require_version(version, record.version)
    if kind == "profile" and not str(values["display_name"]).strip():
        raise AppError(422, "VALIDATION_ERROR", "姓名不能为空")
    for name, value in values.items():
        setattr(record, name, value)
    record.version += 1
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action=f"identity.{kind}.updated",
            resource_type="user",
            resource_id=actor.user_id,
            trace_id=trace_id,
        )
    )
    s.flush()
    return record


def touch_session(s: Session, token: str, now: datetime) -> None:
    record = session_record(s, token, now)
    record.last_seen_at = now


def take_budget(s: Session, key: str, maximum: int, window: timedelta, now: datetime) -> None:
    digest = token_digest(key)
    s.execute(
        insert(AuthLimit)
        .values(key_hash=digest, window_started_at=now, attempts=0)
        .on_conflict_do_nothing()
    )
    record = s.scalar(select(AuthLimit).where(AuthLimit.key_hash == digest).with_for_update())
    assert record is not None
    if now - record.window_started_at >= window:
        record.window_started_at = now
        record.attempts = 0
    if record.attempts >= maximum:
        raise AppError(429, "AUTH_RATE_LIMITED", "尝试次数过多，请稍后再试")
    record.attempts += 1
