from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import JsonObject
from app.infrastructure.db import Base, Entity


class SopPlan(Entity, Base):
    __tablename__ = "sop_plans"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("id", "case_id"),)


class SopRevision(Entity, Base):
    __tablename__ = "sop_revisions"
    plan_id: Mapped[UUID] = mapped_column(Uuid)
    case_id: Mapped[UUID] = mapped_column(Uuid)
    number: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default="draft")
    goal: Mapped[str] = mapped_column(String(1000), default="")
    reminder: Mapped[JsonObject] = mapped_column(JSONB, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["plan_id", "case_id"], ["sop_plans.id", "sop_plans.case_id"]),
        UniqueConstraint("plan_id", "number"),
        UniqueConstraint("id", "case_id"),
        CheckConstraint("state IN ('draft','published','archived')", name="state"),
        CheckConstraint("number >= 1 AND version >= 1 AND schema_version >= 1", name="versions"),
        CheckConstraint("(state <> 'draft') = (published_at IS NOT NULL)", name="publication"),
        Index(
            "uq_sop_current_draft", "plan_id", unique=True, postgresql_where=text("state = 'draft'")
        ),
    )


class SopStep(Base):
    __tablename__ = "sop_steps"
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("sop_revisions.id"), primary_key=True)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    instruction: Mapped[str] = mapped_column(String(2000))
    media_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_seconds: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("revision_id", "position"),
        CheckConstraint("position BETWEEN 1 AND 100", name="position"),
        CheckConstraint(
            "estimated_seconds IS NULL OR estimated_seconds BETWEEN 0 AND 86400", name="duration"
        ),
    )
