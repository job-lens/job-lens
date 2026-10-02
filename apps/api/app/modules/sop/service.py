from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import AppError, conflict, not_found
from app.core.http import require_version
from app.core.types import Actor, JsonObject
from app.infrastructure.assets import link_files, require_files
from app.infrastructure.db import utcnow
from app.infrastructure.models import AuditEvent
from app.infrastructure.pagination import cursor_scope, decode_cursor, encode_cursor
from app.modules.cases.public import CaseAccess
from app.modules.cases.queries import match_confirmed, read_access
from app.modules.sop.models import SopPlan, SopRevision, SopStep
from app.modules.sop.public import PublishedSop
from app.modules.sop.queries import revision_payload
from app.modules.sop.rules import validate_publication

DEFAULT_REMINDER: JsonObject = {
    "speech_enabled": False,
    "vibration_enabled": False,
    "prompt_level": 1,
}


def plan_access(
    s: Session, actor: Actor, plan_id: UUID, lock: bool = False
) -> tuple[SopPlan, CaseAccess]:
    case_id = s.scalar(select(SopPlan.case_id).where(SopPlan.id == plan_id))
    if case_id is None:
        raise not_found()
    access = read_access(s, actor, case_id, lock=lock)
    row = s.scalar(
        select(SopPlan).where(SopPlan.id == plan_id).execution_options(populate_existing=True)
    )
    assert row is not None
    return row, access


def revision_access(
    s: Session, actor: Actor, revision_id: UUID, lock: bool = False
) -> tuple[SopRevision, CaseAccess]:
    case_id = s.scalar(select(SopRevision.case_id).where(SopRevision.id == revision_id))
    if case_id is None:
        raise not_found()
    access = read_access(s, actor, case_id, lock=lock)
    row = s.scalar(
        select(SopRevision)
        .where(SopRevision.id == revision_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    if row.state == "draft" and actor.user_id not in access.counselor_ids:
        raise not_found()
    return row, access


def plan_payload(s: Session, actor: Actor, row: SopPlan) -> dict[str, object]:
    access = read_access(s, actor, row.case_id)
    revisions = s.scalars(
        select(SopRevision).where(SopRevision.plan_id == row.id).order_by(SopRevision.number.desc())
    ).all()
    published = next((r.id for r in revisions if r.state == "published"), None)
    draft = next((r.id for r in revisions if r.state == "draft"), None)
    counselor = "counselor" in actor.roles and actor.user_id in access.counselor_ids
    if published is None and not counselor:
        raise not_found()
    return {
        "id": row.id,
        "case_id": row.case_id,
        "title": row.title,
        "published_revision_id": published,
        "draft_revision_id": draft if counselor else None,
        "version": row.version,
    }


def list_plans(
    s: Session, actor: Actor, case_id: UUID, limit: int, cursor: str | None
) -> tuple[list[dict[str, object]], str | None]:
    access = read_access(s, actor, case_id)
    scope = cursor_scope(actor.user_id, "plans", str(case_id))
    query = select(SopPlan).where(SopPlan.case_id == case_id)
    if "counselor" not in actor.roles or actor.user_id not in access.counselor_ids:
        query = query.where(
            select(SopRevision.id)
            .where(SopRevision.plan_id == SopPlan.id, SopRevision.state == "published")
            .exists()
        )
    after = decode_cursor(cursor, scope)
    if after:
        query = query.where(tuple_(SopPlan.created_at, SopPlan.id) < after)
    rows = list(
        s.scalars(query.order_by(SopPlan.created_at.desc(), SopPlan.id.desc()).limit(limit + 1))
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return [plan_payload(s, actor, row) for row in rows], encode_cursor(
        rows[-1].created_at, rows[-1].id, scope
    ) if more else None


def audit(s: Session, actor: Actor, action: str, row_id: UUID, trace_id: str) -> None:
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action=action,
            resource_type="sop_revision",
            resource_id=row_id,
            trace_id=trace_id,
        )
    )


def create_plan(
    s: Session, actor: Actor, case_id: UUID, title: str, trace_id: str
) -> dict[str, object]:
    read_access(s, actor, case_id, lock=True).require_counselor(actor)
    if not title.strip():
        raise AppError(422, "INVALID_TITLE", "请填写计划名称")
    plan = SopPlan(case_id=case_id, title=title.strip(), author_id=actor.user_id)
    s.add(plan)
    s.flush()
    revision = SopRevision(
        plan_id=plan.id, case_id=case_id, number=1, reminder=dict(DEFAULT_REMINDER)
    )
    s.add(revision)
    s.flush()
    audit(s, actor, "sop.plan_created", revision.id, trace_id)
    return plan_payload(s, actor, plan)


def create_revision(
    s: Session, actor: Actor, plan_id: UUID, base_id: UUID | None, trace_id: str
) -> JsonObject:
    plan, access = plan_access(s, actor, plan_id, True)
    access.require_counselor(actor)
    if s.scalar(
        select(SopRevision.id).where(SopRevision.plan_id == plan_id, SopRevision.state == "draft")
    ):
        raise conflict("CURRENT_DRAFT_EXISTS")
    base = None
    if base_id:
        base = s.get(SopRevision, base_id)
        if base is None or base.plan_id != plan_id or base.state == "draft":
            raise not_found()
    number = (
        s.scalar(select(func.max(SopRevision.number)).where(SopRevision.plan_id == plan_id)) or 0
    ) + 1
    row = SopRevision(
        plan_id=plan.id,
        case_id=plan.case_id,
        number=number,
        goal=base.goal if base else "",
        reminder=dict(base.reminder if base else DEFAULT_REMINDER),
    )
    s.add(row)
    s.flush()
    if base:
        for step in s.scalars(select(SopStep).where(SopStep.revision_id == base.id)):
            s.add(
                SopStep(
                    revision_id=row.id,
                    id=step.id,
                    position=step.position,
                    instruction=step.instruction,
                    media_ids=list(step.media_ids),
                    evidence_required=step.evidence_required,
                    estimated_seconds=step.estimated_seconds,
                )
            )
    plan.version += 1
    audit(s, actor, "sop.draft_created", row.id, trace_id)
    s.flush()
    return revision_payload(s, row)


def save_revision(
    s: Session, actor: Actor, revision_id: UUID, body: JsonObject, version: str, trace_id: str
) -> JsonObject:
    row, access = revision_access(s, actor, revision_id, True)
    access.require_counselor(actor)
    require_version(version, row.version)
    if row.state != "draft":
        raise conflict()
    steps = cast(list[JsonObject], body["steps"])
    ids = [str(step["id"]) for step in steps]
    if len(set(ids)) != len(ids) or [step["position"] for step in steps] != list(
        range(1, len(steps) + 1)
    ):
        raise AppError(422, "INVALID_STEPS", "步骤标识或顺序无效")
    for step in steps:
        require_files(
            s, [UUID(str(i)) for i in cast(list[str], step["media_ids"])], row.case_id, "sop_media"
        )
    s.execute(delete(SopStep).where(SopStep.revision_id == row.id))
    s.flush()
    for step in steps:
        s.add(
            SopStep(
                revision_id=row.id,
                id=UUID(str(step["id"])),
                position=int(cast(int, step["position"])),
                instruction=str(step["instruction"]),
                media_ids=cast(list[str], step["media_ids"]),
                evidence_required=bool(step["evidence_required"]),
                estimated_seconds=cast(int, step["estimated_seconds"]),
            )
        )
    row.goal = str(body["goal"])
    row.reminder = cast(JsonObject, body["reminder"])
    row.version += 1
    audit(s, actor, "sop.draft_saved", row.id, trace_id)
    s.flush()
    return revision_payload(s, row)


def publish(s: Session, actor: Actor, revision_id: UUID, version: str, trace_id: str) -> JsonObject:
    row, access = revision_access(s, actor, revision_id, True)
    require_version(version, row.version)
    steps = list(
        s.scalars(select(SopStep).where(SopStep.revision_id == row.id).order_by(SopStep.position))
    )
    ids = [UUID(i) for step in steps for i in step.media_ids]
    require_files(s, list(dict.fromkeys(ids)), row.case_id, "sop_media")
    validate_publication(
        actor,
        access,
        PublishedSop(row.id, row.case_id, tuple(step.id for step in steps)),
        state=row.state,
        match_confirmed=match_confirmed(s, actor, row.case_id),
        goal=row.goal,
        instructions=tuple(step.instruction for step in steps),
        materials_ready=True,
        has_active_task=False,
    )  # Training creates the task in the same HTTP transaction and checks its unique slot.
    row.state = "published"
    row.published_at = utcnow()
    row.version += 1
    plan = s.get(SopPlan, row.plan_id)
    assert plan is not None
    plan.version += 1
    link_files(s, list(dict.fromkeys(ids)), row.case_id, "sop_revision", row.id)
    audit(s, actor, "sop.published", row.id, trace_id)
    s.flush()
    return revision_payload(s, row)
