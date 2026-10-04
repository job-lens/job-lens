"""Verified email registration and one-time password reset.

Reuse Qunxue's code TTL, cooldown, attempt limit and digest-only persistence.
Credential generations revoke every old session atomically, including a login
that races a reset, without locking every session row in a different order.
"""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import hash_password, new_token, token_digest, verify_password
from app.infrastructure.email import require_delivery, send_email
from app.infrastructure.models import AuditEvent
from app.modules.identity.models import EmailChallenge, Preferences, Profile, User, UserRole
from app.modules.identity.queries import load_user, resolve_actor
from app.modules.identity.service import SessionGrant, issue_session, take_budget


def invalid_challenge() -> AppError:
    return AppError(400, "INVALID_CHALLENGE", "验证码或链接已失效，请重新获取")


def email_budget(s: Session, email: str, purpose: str, client: str, now: datetime) -> None:
    # All budgets run before account lookup, so unknown addresses use the same limits.
    take_budget(s, purpose + ":global", 120, timedelta(hours=1), now)
    take_budget(s, purpose + ":client:" + client, 20, timedelta(hours=1), now)
    take_budget(s, purpose + ":email:" + email, 5, timedelta(hours=1), now)
    take_budget(s, purpose + ":cooldown:" + email, 1, timedelta(seconds=60), now)


def request_email(
    s: Session,
    config: Settings,
    email: str,
    purpose: str,
    client: str,
    now: datetime,
    trace_id: str = "unknown",
) -> None:
    require_delivery(config, trace_id)
    email_budget(s, email, purpose, client, now)
    with s.begin_nested():
        record = s.scalar(
            select(EmailChallenge)
            .where(EmailChallenge.email == email, EmailChallenge.purpose == purpose)
            .with_for_update()
        )
        if record is None:
            record = EmailChallenge(email=email, purpose=purpose)
        record.created_at = now
        record.consumed_at = None
        record.attempts = 0
        if purpose == "registration":
            code = f"{secrets.randbelow(1000000):06d}"
            record.code_hash = hash_password("mail-code:" + code)
            record.token_hash = None
            record.user_id = None
            record.expires_at = now + timedelta(minutes=5)
            text = f"融职境注册验证码：{code}\n5 分钟内有效。若不是你发起的请求，请忽略此邮件。"
            subject = "融职境 · 注册验证码"
        else:
            token = new_token()
            record.code_hash = None
            record.token_hash = token_digest(token)
            record.user_id = s.scalar(
                select(User.id).where(User.login_name == email, User.active.is_(True))
            )
            record.expires_at = now + timedelta(minutes=15)
            # Send the same message for registered/unknown addresses. Only a token
            # linked to an active account can reset it; neither response enumerates users.
            text = f"如果此邮箱已注册融职境，可在 15 分钟内打开以下链接设置新密码：\n{config.public_origin}/reset-password#token={token}\n若不是你发起的请求，请忽略此邮件。"
            subject = "融职境 · 设置新密码"
        s.add(record)
        s.flush()
        send_email(config, email, subject, text, trace_id)


def register(
    s: Session,
    email: str,
    code: str,
    password: str,
    display_name: str,
    now: datetime,
    trace_id: str,
) -> SessionGrant:
    record = s.scalar(
        select(EmailChallenge)
        .where(EmailChallenge.email == email, EmailChallenge.purpose == "registration")
        .with_for_update()
    )
    if (
        record is None
        or record.consumed_at is not None
        or record.expires_at <= now
        or record.attempts >= 5
    ):
        raise invalid_challenge()
    record.attempts += 1
    if not verify_password("mail-code:" + code, record.code_hash or ""):
        raise invalid_challenge()
    if not display_name.strip():
        raise AppError(422, "VALIDATION_ERROR", "姓名不能为空")
    try:
        with s.begin_nested():
            if s.scalar(select(User.id).where(User.login_name == email)):
                raise AppError(409, "EMAIL_REGISTERED", "此邮箱已注册，请登录或找回密码")
            user = User(login_name=email, password_hash=hash_password(password))
            s.add(user)
            s.flush()
            s.add_all(
                [
                    UserRole(user_id=user.id, role="learner"),
                    Profile(user_id=user.id, display_name=display_name.strip()),
                    Preferences(
                        user_id=user.id,
                        quiet_mode=True,
                        speech_enabled=False,
                        vibration_enabled=False,
                    ),
                ]
            )
            record.consumed_at = now
            s.flush()
            grant = issue_session(s, user.id, now)
            view = load_user(s, resolve_actor(s, grant.token or "", now))
            s.add(
                AuditEvent(
                    actor_id=user.id,
                    action="identity.register",
                    resource_type="user",
                    resource_id=user.id,
                    trace_id=trace_id,
                )
            )
    except IntegrityError:
        raise AppError(409, "EMAIL_REGISTERED", "此邮箱已注册，请登录或找回密码") from None
    return SessionGrant(grant.token, grant.csrf_token, view)


def reset_password(s: Session, token: str, password: str, now: datetime, trace_id: str) -> None:
    record = s.scalar(
        select(EmailChallenge)
        .where(EmailChallenge.token_hash == token_digest(token), EmailChallenge.purpose == "reset")
        .with_for_update()
    )
    if (
        record is None
        or record.consumed_at is not None
        or record.expires_at <= now
        or record.user_id is None
    ):
        raise invalid_challenge()
    user = s.scalar(select(User).where(User.id == record.user_id).with_for_update())
    if user is None or not user.active:
        raise invalid_challenge()
    user.password_hash = hash_password(password)
    user.credential_version += 1
    record.consumed_at = now
    s.add(
        AuditEvent(
            actor_id=user.id,
            action="identity.password_reset",
            resource_type="user",
            resource_id=user.id,
            trace_id=trace_id,
        )
    )
