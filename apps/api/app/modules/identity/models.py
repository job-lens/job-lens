from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base, Entity


class User(Entity, Base):
    __tablename__ = "users"
    login_name: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    management_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    credential_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    __table_args__ = (CheckConstraint("credential_version >= 1", name="credential_version"),)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), primary_key=True)
    __table_args__ = (CheckConstraint("role IN ('learner','counselor')", name="role"),)


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    sensory_preferences: Mapped[list[str]] = mapped_column(JSONB, default=list)
    communication_preference: Mapped[str] = mapped_column(String(200), default="")
    work_notes: Mapped[str] = mapped_column(String(1000), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (CheckConstraint("version >= 1", name="version"),)


class Preferences(Base):
    __tablename__ = "preferences"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    font_scale: Mapped[float] = mapped_column(Float, default=1)
    volume: Mapped[float] = mapped_column(Float, default=0.5)
    quiet_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    speech_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    vibration_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        CheckConstraint("font_scale IN (1,1.25,1.5)", name="font_scale"),
        CheckConstraint("volume BETWEEN 0 AND 1", name="volume"),
        CheckConstraint("version >= 1", name="version"),
    )


class SessionRecord(Entity, Base):
    __tablename__ = "sessions"
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    __table_args__ = (CheckConstraint("credential_version >= 1", name="credential_version"),)


class EmailChallenge(Entity, Base):
    __tablename__ = "email_challenges"
    email: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    code_hash: Mapped[str | None] = mapped_column(String(255))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("email", "purpose"),
        CheckConstraint("purpose IN ('registration','reset')", name="purpose"),
        CheckConstraint("attempts BETWEEN 0 AND 5", name="attempts"),
        CheckConstraint(
            "(purpose = 'registration' AND code_hash IS NOT NULL AND token_hash IS NULL) OR (purpose = 'reset' AND token_hash IS NOT NULL AND code_hash IS NULL)",
            name="digest",
        ),
    )


class ExternalIdentity(Entity, Base):
    __tablename__ = "external_identities"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("provider", "subject"),)


class AuthLimit(Base):
    __tablename__ = "auth_limits"
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("attempts >= 0", name="attempts"),)


class AdministratorGrant(Base):
    """Explicit operator-managed capability; registration can never create this row."""

    __tablename__ = "administrator_grants"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CounselorCertification(Base):
    __tablename__ = "counselor_certifications"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    state: Mapped[str] = mapped_column(String(20), default="not_submitted")
    statement: Mapped[str] = mapped_column(String(2000), default="")
    reason: Mapped[str] = mapped_column(String(1000), default="")
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        CheckConstraint(
            "state IN ('not_submitted','pending','approved','rejected','revoked')", name="state"
        ),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("reviewer_id IS NULL OR reviewer_id != user_id", name="no_self_review"),
    )


class ManagementEvent(Entity, Base):
    """Append-only application audit, excluding application statements and private profiles."""

    __tablename__ = "management_events"
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    target_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(1000))
    trace_id: Mapped[str] = mapped_column(String(128))
