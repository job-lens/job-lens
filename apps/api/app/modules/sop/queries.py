from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.core.types import Actor, JsonObject, JsonValue
from app.modules.cases.queries import read_access
from app.modules.sop.models import SopPlan, SopRevision, SopStep


@dataclass(frozen=True)
class RevisionSnapshot:
    case_id: UUID
    title: str
    content: JsonObject


def revision_payload(s: Session, revision: SopRevision) -> JsonObject:
    rows = s.scalars(
        select(SopStep).where(SopStep.revision_id == revision.id).order_by(SopStep.position)
    ).all()
    return {
        "id": str(revision.id),
        "plan_id": str(revision.plan_id),
        "revision_no": revision.number,
        "state": revision.state,
        "version": revision.version,
        "goal": revision.goal,
        "reminder": revision.reminder,
        "published_at": revision.published_at.isoformat() if revision.published_at else None,
        "steps": [
            {
                "id": str(row.id),
                "position": row.position,
                "instruction": row.instruction,
                "media_ids": cast(JsonValue, row.media_ids),
                "estimated_seconds": row.estimated_seconds or 0,
                "evidence_required": row.evidence_required,
            }
            for row in rows
        ],
    }


def published_snapshot(s: Session, actor: Actor, revision_id: UUID) -> RevisionSnapshot:
    revision = s.get(SopRevision, revision_id)
    if revision is None or revision.state == "draft":
        raise not_found()
    read_access(s, actor, revision.case_id)
    plan = s.get(SopPlan, revision.plan_id)
    assert plan is not None
    return RevisionSnapshot(revision.case_id, plan.title, revision_payload(s, revision))
