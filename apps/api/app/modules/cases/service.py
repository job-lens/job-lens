from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.core.http import require_version
from app.core.types import Actor
from app.infrastructure.models import AuditEvent, FileAsset
from app.infrastructure.pagination import cursor_scope, decode_cursor, encode_cursor
from app.modules.cases.models import Case, CaseGrant, SupportMatch
from app.modules.cases.queries import read_access, scope_predicate
from app.modules.identity.queries import profile_snapshot


def list_cases(
    s: Session, actor: Actor, limit: int, cursor: str | None, state: str | None
) -> tuple[list[dict[str, object]], str | None]:
    scope = cursor_scope(actor.user_id, "cases", state or "")
    query = select(Case).where(scope_predicate(actor))
    if state:
        query = query.where(Case.lifecycle == state)
    after = decode_cursor(cursor, scope)
    if after:
        query = query.where(tuple_(Case.created_at, Case.id) < after)
    rows = list(s.scalars(query.order_by(Case.created_at.desc(), Case.id.desc()).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    grants = s.execute(
        select(CaseGrant.case_id, CaseGrant.counselor_id)
        .where(CaseGrant.case_id.in_([row.id for row in rows]), CaseGrant.revoked_at.is_(None))
        .order_by(CaseGrant.counselor_id)
    ).all()
    counselors: dict[UUID, UUID] = {}
    for case_id, user_id in grants:
        if case_id not in counselors or user_id == actor.user_id:
            counselors[case_id] = user_id
    items: list[dict[str, object]] = [
        {
            "id": row.id,
            "learner_id": row.learner_id,
            "counselor_id": counselors.get(row.id),
            "lifecycle": row.lifecycle,
            "version": row.version,
        }
        for row in rows
    ]
    return items, encode_cursor(rows[-1].created_at, rows[-1].id, scope) if more else None


def get_case(s: Session, actor: Actor, case_id: UUID) -> dict[str, object]:
    access = read_access(s, actor, case_id)
    row = s.get(Case, case_id)
    assert row is not None
    return {
        "id": row.id,
        "learner_id": row.learner_id,
        "counselor_id": actor.user_id
        if actor.user_id in access.counselor_ids
        else next(iter(sorted(access.counselor_ids)), None),
        "lifecycle": row.lifecycle,
        "version": row.version,
    }


def get_profile(s: Session, actor: Actor, case_id: UUID) -> dict[str, object]:
    access = read_access(s, actor, case_id)
    return profile_snapshot(s, access.learner_id)


def get_match(s: Session, actor: Actor, case_id: UUID) -> SupportMatch:
    read_access(s, actor, case_id)
    row = s.scalar(select(SupportMatch).where(SupportMatch.case_id == case_id))
    if row is None:
        raise not_found()
    return row


def save_match(
    s: Session, actor: Actor, case_id: UUID, body: dict[str, object], version: str, trace_id: str
) -> SupportMatch:
    read_access(s, actor, case_id, lock=True).require_counselor(actor)
    row = get_match(s, actor, case_id)
    require_version(version, row.version)
    if row.state != "draft":
        raise conflict()
    for key, value in body.items():
        setattr(row, key, value)
    row.version += 1
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action="cases.match_saved",
            resource_type="case",
            resource_id=case_id,
            trace_id=trace_id,
        )
    )
    s.flush()
    return row


def confirm_match(
    s: Session, actor: Actor, case_id: UUID, version: str, trace_id: str
) -> SupportMatch:
    read_access(s, actor, case_id, lock=True).require_counselor(actor)
    row = get_match(s, actor, case_id)
    require_version(version, row.version)
    case = s.get(Case, case_id)
    assert case is not None
    if row.state != "draft" or case.lifecycle != "pending_match":
        raise conflict()
    if any(not value.strip() for value in (row.direction, row.focus, row.basis)):
        raise conflict("INCOMPLETE_MATCH")
    row.state = "confirmed"
    row.version += 1
    case.lifecycle = "active"
    case.version += 1
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action="cases.match_confirmed",
            resource_type="case",
            resource_id=case_id,
            trace_id=trace_id,
        )
    )
    s.flush()
    return row


def materials(
    s: Session, actor: Actor, case_id: UUID, limit: int, cursor: str | None
) -> tuple[list[FileAsset], str | None]:
    access = read_access(s, actor, case_id)
    scope = cursor_scope(actor.user_id, "materials", str(case_id))
    query = select(FileAsset).where(
        FileAsset.case_id == case_id,
        FileAsset.purpose == "profile_material",
        FileAsset.state != "deleted",
    )
    if actor.user_id != access.learner_id:
        query = query.where(FileAsset.state == "ready")
    after = decode_cursor(cursor, scope)
    if after:
        query = query.where(tuple_(FileAsset.created_at, FileAsset.id) < after)
    rows = list(
        s.scalars(query.order_by(FileAsset.created_at.desc(), FileAsset.id.desc()).limit(limit + 1))
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, encode_cursor(rows[-1].created_at, rows[-1].id, scope) if more else None
