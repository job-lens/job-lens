import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.errors import AppError

_HASHER = PasswordHasher()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 256:
        raise ValueError("password length must be 12..256")
    return _HASHER.hash(password)


def verify_password(password: str, digest: str) -> bool:
    if not 1 <= len(password) <= 256:
        return False
    try:
        return _HASHER.verify(digest, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_csrf(origin: str | None, expected_origin: str, token: str | None, digest: str) -> None:
    if origin != expected_origin or not token or not 16 <= len(token) <= 256:
        raise AppError(403, "CSRF_REJECTED", "请求校验失败")
    if not hmac.compare_digest(token_digest(token), digest):
        raise AppError(403, "CSRF_REJECTED", "请求校验失败")


@dataclass(frozen=True)
class SessionWindow:
    created_at: datetime
    last_seen_at: datetime
    revoked: bool = False

    def valid_at(self, now: datetime) -> bool:
        if any(t.tzinfo is None for t in (self.created_at, self.last_seen_at, now)):
            raise ValueError("session timestamps must be timezone-aware")
        return (
            not self.revoked
            and self.created_at <= self.last_seen_at <= now
            and now - self.created_at < timedelta(hours=12)
            and now - self.last_seen_at < timedelta(hours=2)
        )
