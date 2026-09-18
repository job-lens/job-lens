from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.types import JsonObject
from app.infrastructure.db import utcnow
from app.infrastructure.models import Job


@dataclass(frozen=True)
class Lease:
    job_id: UUID
    token: UUID
    kind: str
    payload: JsonObject
    seconds: int


def enqueue(session: Session, kind: str, payload: JsonObject, dedupe_key: str) -> UUID:
    statement = (
        insert(Job)
        .values(
            id=uuid4(),
            created_at=utcnow(),
            kind=kind,
            payload=payload,
            dedupe_key=dedupe_key,
            state="pending",
            attempts=0,
            max_attempts=5,
            next_run_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=[Job.dedupe_key])
        .returning(Job.id)
    )
    job_id = session.scalar(statement)
    if job_id is None:
        row = session.scalar(select(Job).where(Job.dedupe_key == dedupe_key))
        if row is None or row.kind != kind or row.payload != payload:
            raise ValueError("job dedupe key reused for different content")
        return row.id
    return job_id


def claim(session: Session, lease_seconds: int = 60) -> Lease | None:
    if not 10 <= lease_seconds <= 3600:
        raise ValueError("lease_seconds must be 10..3600")
    now = session.scalar(select(func.now()))
    if now is None:
        raise RuntimeError("database time unavailable")
    session.execute(
        update(Job)
        .where(
            Job.state == "running",
            Job.lease_until <= now,
            Job.attempts >= Job.max_attempts,
        )
        .values(state="failed", lease_token=None, lease_until=None, error_code="LEASE_EXHAUSTED")
    )
    job = session.scalar(
        select(Job)
        .where(
            Job.attempts < Job.max_attempts,
            or_(
                and_(Job.state == "pending", Job.next_run_at <= now),
                and_(Job.state == "running", Job.lease_until <= now),
            ),
        )
        .order_by(Job.next_run_at, Job.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.state = "running"
    job.attempts += 1
    job.lease_token = uuid4()
    job.lease_until = now + timedelta(seconds=lease_seconds)
    session.flush()
    return Lease(job.id, job.lease_token, job.kind, job.payload, lease_seconds)


def renew(session: Session, lease: Lease) -> bool:
    now = session.scalar(select(func.now()))
    if now is None:
        raise RuntimeError("database time unavailable")
    result = session.execute(
        update(Job)
        .where(
            Job.id == lease.job_id,
            Job.state == "running",
            Job.lease_token == lease.token,
            Job.lease_until > now,
        )
        .values(lease_until=now + timedelta(seconds=lease.seconds))
        .returning(Job.id)
    )
    return result.scalar_one_or_none() is not None


def finish(session: Session, lease: Lease, error_code: str | None = None) -> bool:
    now = session.scalar(select(func.now()))
    if now is None:
        raise RuntimeError("database time unavailable")
    job = session.scalar(
        select(Job)
        .where(
            Job.id == lease.job_id,
            Job.state == "running",
            Job.lease_token == lease.token,
            Job.lease_until > now,
        )
        .with_for_update()
    )
    if job is None:
        return False
    if error_code is None:
        job.state = "done"
    else:
        job.state = (
            "failed"
            if job.attempts >= job.max_attempts or error_code == "UNKNOWN_HANDLER"
            else "pending"
        )
        job.error_code = error_code[:80]
        job.next_run_at = now + timedelta(seconds=min(2**job.attempts, 60))
    job.lease_until = None
    job.lease_token = None
    session.flush()
    return True
