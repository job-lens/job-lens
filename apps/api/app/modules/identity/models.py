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


class ExternalIdentity(Entity, Base):
    __tablename__ = "external_identities"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("provider", "subject"),)
