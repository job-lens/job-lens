from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import JsonObject
from app.infrastructure.db import Base, Entity


class Assistance(Entity, Base):
    __tablename__ = "assistance_requests"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"))
    task_id: Mapped[UUID | None] = mapped_column(Uuid)
    step_id: Mapped[UUID | None] = mapped_column(Uuid)
    revision_id: Mapped[UUID | None] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(16), default="queued")
    message: Mapped[str] = mapped_column(String(500))
    attachment_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    preferred_mode: Mapped[str] = mapped_column(String(16), default="text")
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "case_id"], ["training_tasks.id", "training_tasks.case_id"]
        ),
        CheckConstraint("state IN ('queued','accepted','resolved','cancelled')", name="state"),
        CheckConstraint("step_id IS NULL OR task_id IS NOT NULL", name="step_context"),
        CheckConstraint("(task_id IS NULL) = (revision_id IS NULL)", name="revision_context"),
        ForeignKeyConstraint(
            ["task_id", "revision_id"], ["training_tasks.id", "training_tasks.revision_id"]
        ),
        ForeignKeyConstraint(["revision_id", "step_id"], ["sop_steps.revision_id", "sop_steps.id"]),
        CheckConstraint("preferred_mode IN ('text','annotation')", name="mode"),
        CheckConstraint("version >= 1", name="version"),
        Index(
            "uq_open_assistance",
            "case_id",
            "task_id",
            unique=True,
            postgresql_where=text("state IN ('queued','accepted')"),
            postgresql_nulls_not_distinct=True,
        ),
    )


class SupportMessage(Entity, Base):
    __tablename__ = "support_messages"
    request_id: Mapped[UUID] = mapped_column(ForeignKey("assistance_requests.id"), index=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(String(2000), default="")
    attachment_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    __table_args__ = (
        CheckConstraint(
            "length(trim(body)) > 0 OR jsonb_array_length(attachment_ids) > 0", name="content"
        ),
    )


class Annotation(Entity, Base):
    __tablename__ = "annotations"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"))
    task_id: Mapped[UUID] = mapped_column(Uuid)
    asset_id: Mapped[UUID] = mapped_column(Uuid)
    submission_id: Mapped[UUID | None] = mapped_column(Uuid)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default="draft")
    markers: Mapped[list[JsonObject]] = mapped_column(JSONB, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "case_id"], ["training_tasks.id", "training_tasks.case_id"]
        ),
        ForeignKeyConstraint(["asset_id", "case_id"], ["file_assets.id", "file_assets.case_id"]),
        ForeignKeyConstraint(
            ["submission_id", "task_id"], ["submissions.id", "submissions.task_id"]
        ),
        CheckConstraint("kind IN ('question','guidance')", name="kind"),
        CheckConstraint("state IN ('draft','published')", name="state"),
        CheckConstraint("version >= 1", name="version"),
    )
