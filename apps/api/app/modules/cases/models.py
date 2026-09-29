from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base, Entity


class Case(Entity, Base):
    __tablename__ = "cases"
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    lifecycle: Mapped[str] = mapped_column(String(20), default="pending_match")
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        CheckConstraint("lifecycle IN ('pending_match','active','closed')", name="lifecycle"),
        CheckConstraint("version >= 1", name="version"),
    )


class CaseGrant(Base):
    __tablename__ = "case_grants"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    counselor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportMatch(Entity, Base):
    __tablename__ = "support_matches"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), unique=True)
    direction: Mapped[str] = mapped_column(String(80), default="")
    focus: Mapped[str] = mapped_column(String(500), default="")
    basis: Mapped[str] = mapped_column(String(1000), default="")
    cycle_weeks: Mapped[int] = mapped_column(Integer, default=4)
    state: Mapped[str] = mapped_column(String(16), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        CheckConstraint("state IN ('draft','confirmed')", name="state"),
        CheckConstraint("cycle_weeks BETWEEN 1 AND 52", name="cycle"),
        CheckConstraint("version >= 1", name="version"),
        UniqueConstraint("id", "case_id"),
    )
