from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import JsonObject, JsonValue
from app.infrastructure.db import Base, Entity, utcnow


class FileAsset(Entity, Base):
    __tablename__ = "file_assets"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"))
    task_id: Mapped[UUID | None] = mapped_column(Uuid)
    uploader_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(String(24))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="quarantined")
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        UniqueConstraint("id", "case_id"),
        ForeignKeyConstraint(
            ["task_id", "case_id"], ["training_tasks.id", "training_tasks.case_id"]
        ),
        CheckConstraint(
            "state IN ('quarantined','scanning','ready','rejected','deleted')", name="state"
        ),
        CheckConstraint(
            "purpose IN ('profile_material','task_evidence','sop_media','support_message')",
            name="purpose",
        ),
        CheckConstraint("size_bytes BETWEEN 1 AND 20971520 AND version >= 1", name="bounds"),
    )


class FileLink(Entity, Base):
    __tablename__ = "file_links"
    asset_id: Mapped[UUID] = mapped_column(Uuid)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"))
    owner_kind: Mapped[str] = mapped_column(String(24))
    owner_id: Mapped[UUID] = mapped_column(Uuid)
    __table_args__ = (
        ForeignKeyConstraint(["asset_id", "case_id"], ["file_assets.id", "file_assets.case_id"]),
        UniqueConstraint("asset_id", "owner_kind", "owner_id"),
        CheckConstraint(
            "owner_kind IN ('sop_revision','submission','support_message','annotation')",
            name="owner_kind",
        ),
    )


class NotificationCounter(Base):
    __tablename__ = "notification_counters"
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, default=0)
    retained_after: Mapped[int] = mapped_column(BigInteger, default=0)
    __table_args__ = (
        CheckConstraint("seq >= retained_after AND retained_after >= 0", name="sequence"),
    )


class Notification(Entity, Base):
    __tablename__ = "notifications"
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    seq: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[UUID] = mapped_column(Uuid)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("recipient_id", "seq"),
        CheckConstraint("seq > 0", name="sequence"),
    )


class Job(Entity, Base):
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(String(80))
    payload: Mapped[JsonObject] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (
        CheckConstraint("state IN ('pending','running','done','failed')", name="state"),
        CheckConstraint("attempts >= 0 AND max_attempts BETWEEN 1 AND 20", name="attempts"),
        CheckConstraint(
            "(state = 'running') = (lease_token IS NOT NULL AND lease_until IS NOT NULL)",
            name="lease",
        ),
    )


class IdempotencyRecord(Entity, Base):
    __tablename__ = "idempotency_records"
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(255))
    key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[JsonValue] = mapped_column(JSONB, nullable=True)
    response_headers: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (
        UniqueConstraint("actor_id", "method", "path", "key", name="uq_idempotency_scope"),
    )


class AuditEvent(Entity, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[UUID] = mapped_column(Uuid)
    trace_id: Mapped[str] = mapped_column(String(128))
