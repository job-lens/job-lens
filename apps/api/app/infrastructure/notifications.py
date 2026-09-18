from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.infrastructure.db import utcnow
from app.infrastructure.models import Notification, NotificationCounter


@dataclass(frozen=True)
class NotificationPage:
    items: tuple[Notification, ...]
    next_seq: str
    has_more: bool


def append_notifications(
    session: Session,
    recipients: set[UUID],
    kind: str,
    resource_type: str,
    resource_id: UUID,
) -> tuple[Notification, ...]:
    result = []
    # A stable lock order prevents deadlocks when one transaction has several recipients.
    for recipient in sorted(recipients):
        session.execute(
            insert(NotificationCounter)
            .values(
                recipient_id=recipient,
                seq=0,
                retained_after=0,
            )
            .on_conflict_do_nothing()
        )
        counter = session.scalar(
            select(NotificationCounter)
            .where(
                NotificationCounter.recipient_id == recipient,
            )
            .with_for_update()
        )
        if counter is None:
            raise RuntimeError("notification counter not found")
        counter.seq += 1
        row = Notification(
            id=uuid4(),
            recipient_id=recipient,
            seq=counter.seq,
            kind=kind,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        session.add(row)
        result.append(row)
    session.flush()
    return tuple(result)


def read_notifications(
    session: Session, recipient: UUID, after: int = 0, limit: int = 20
) -> NotificationPage:
    if after < 0 or not 1 <= limit <= 100:
        raise AppError(400, "INVALID_CURSOR", "分页参数无效")
    counter = session.get(NotificationCounter, recipient)
    if after and (counter is None or after > counter.seq):
        raise AppError(400, "INVALID_CURSOR", "通知游标无效")
    if counter is not None and after and after < counter.retained_after:
        raise AppError(410, "CURSOR_EXPIRED", "请重新同步通知")
    rows = session.scalars(
        select(Notification)
        .where(
            Notification.recipient_id == recipient,
            Notification.seq > after,
        )
        .order_by(Notification.seq)
        .limit(limit + 1)
    ).all()
    items = tuple(rows[:limit])
    return NotificationPage(items, str(items[-1].seq if items else after), len(rows) > limit)


def mark_read(session: Session, recipient: UUID, notification_id: UUID) -> None:
    row = session.scalar(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_id == recipient,
        )
        .with_for_update()
    )
    if row is None:
        raise not_found()
    if row.read_at is None:
        row.read_at = utcnow()
