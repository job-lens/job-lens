from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
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


class TrainingTask(Entity, Base):
    __tablename__ = "training_tasks"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"))
    revision_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    status: Mapped[str] = mapped_column(String(24), default="not_started")
    due_on: Mapped[date | None] = mapped_column(Date)
    prompt_override: Mapped[int | None] = mapped_column(Integer)
    prompt_reason: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        ForeignKeyConstraint(
            ["revision_id", "case_id"], ["sop_revisions.id", "sop_revisions.case_id"]
        ),
        UniqueConstraint("id", "revision_id"),
        UniqueConstraint("id", "case_id"),
        CheckConstraint(
            "status IN ('not_started','in_progress','paused','submitted','changes_requested','completed','cancelled')",
            name="status",
        ),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(
            "(prompt_override IS NULL AND prompt_reason IS NULL) OR (prompt_override IS NOT NULL AND prompt_override BETWEEN 1 AND 3 AND prompt_reason IS NOT NULL AND length(trim(prompt_reason)) BETWEEN 1 AND 500)",
            name="prompt",
        ),
        Index(
            "uq_case_active_task",
            "case_id",
            unique=True,
            postgresql_where=text("status NOT IN ('completed','cancelled')"),
        ),
    )


class StepProgress(Base):
    __tablename__ = "step_progress"
    task_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    step_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attachment_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "revision_id"], ["training_tasks.id", "training_tasks.revision_id"]
        ),
        ForeignKeyConstraint(["revision_id", "step_id"], ["sop_steps.revision_id", "sop_steps.id"]),
        CheckConstraint("status IN ('pending','in_progress','completed')", name="status"),
    )


class TaskEvent(Entity, Base):
    __tablename__ = "task_events"
    task_id: Mapped[UUID] = mapped_column(ForeignKey("training_tasks.id"), index=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    revision_id: Mapped[UUID] = mapped_column(Uuid)
    session_id: Mapped[UUID] = mapped_column(Uuid)
    step_id: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    value: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "revision_id"], ["training_tasks.id", "training_tasks.revision_id"]
        ),
        ForeignKeyConstraint(["revision_id", "step_id"], ["sop_steps.revision_id", "sop_steps.id"]),
        CheckConstraint(
            "kind IN ('hint_requested','self_reported_error','time_sample')", name="kind"
        ),
        CheckConstraint(
            "sequence >= 1 AND (value IS NULL OR value BETWEEN 0 AND 86400000)", name="values"
        ),
    )


class Submission(Entity, Base):
    __tablename__ = "submissions"
    task_id: Mapped[UUID] = mapped_column(ForeignKey("training_tasks.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(500), default="")
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    snapshot: Mapped[JsonObject] = mapped_column(JSONB)
    __table_args__ = (
        UniqueConstraint("task_id", "attempt_no"),
        UniqueConstraint("id", "task_id"),
        CheckConstraint("attempt_no >= 1 AND schema_version >= 1", name="versions"),
    )


class Feedback(Entity, Base):
    __tablename__ = "feedback"
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("submissions.id"), unique=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(String(24))
    message: Mapped[str] = mapped_column(String(500))
    redo_step_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    annotation_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    __table_args__ = (
        CheckConstraint("outcome IN ('passed','changes_requested')", name="outcome"),
        CheckConstraint("length(trim(message)) > 0", name="message"),
        CheckConstraint(
            "(outcome = 'changes_requested') = (jsonb_array_length(redo_step_ids) > 0)", name="redo"
        ),
    )
