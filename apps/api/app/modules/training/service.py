from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError, conflict, not_found
from app.core.http import require_version
from app.core.types import Actor, JsonObject, JsonValue
from app.infrastructure.assets import link_files, require_files
from app.infrastructure.models import AuditEvent
from app.infrastructure.notifications import append_notifications
from app.infrastructure.pagination import cursor_scope, decode_cursor, encode_cursor
from app.modules.cases.public import CaseAccess
from app.modules.cases.queries import authorized_case_ids, read_access
from app.modules.sop.queries import published_snapshot
from app.modules.training.models import Feedback, StepProgress, Submission, TaskEvent, TrainingTask
from app.modules.training.public import TaskStatus
from app.modules.training.rules import transition, validate_feedback


def create_for_publication(
    s: Session, actor: Actor, revision_id: UUID, due_on: date | None, trace_id: str
) -> TrainingTask:
    snapshot = published_snapshot(s, actor, revision_id)
    access = read_access(s, actor, snapshot.case_id, lock=True)
    access.require_counselor(actor)
    if s.scalar(
        select(TrainingTask.id).where(
            TrainingTask.case_id == snapshot.case_id,
            TrainingTask.status.not_in(["completed", "cancelled"]),
        )
    ):
        raise conflict("ACTIVE_TASK_EXISTS")
    task = TrainingTask(case_id=snapshot.case_id, revision_id=revision_id, due_on=due_on)
    s.add(task)
    s.flush()
    for step in cast(list[JsonObject], snapshot.content["steps"]):
        s.add(StepProgress(task_id=task.id, step_id=UUID(str(step["id"])), revision_id=revision_id))
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action="training.created",
            resource_type="task",
            resource_id=task.id,
            trace_id=trace_id,
        )
    )
    append_notifications(s, {access.learner_id}, "training.created", "task", task.id)
    s.flush()
    return task


def task_access(
    s: Session, actor: Actor, task_id: UUID, lock: bool = False
) -> tuple[TrainingTask, CaseAccess]:
    case_id = s.scalar(select(TrainingTask.case_id).where(TrainingTask.id == task_id))
    if case_id is None:
        raise not_found()
    access = read_access(s, actor, case_id, lock=lock)
    task = s.scalar(
        select(TrainingTask)
        .where(TrainingTask.id == task_id)
        .execution_options(populate_existing=True)
    )
    assert task is not None
    return task, access


def progress_payload(s: Session, actor: Actor, task: TrainingTask) -> list[JsonObject]:
    rows = {
        row.step_id: row
        for row in s.scalars(select(StepProgress).where(StepProgress.task_id == task.id))
    }
    # The fixed revision determines display order, including selected steps after rework.
    snapshot = published_snapshot(s, actor, task.revision_id)
    return [
        {
            "step_id": str(step["id"]),
            "status": rows[UUID(str(step["id"]))].status,
            "attachment_ids": cast(JsonValue, list(rows[UUID(str(step["id"]))].attachment_ids)),
        }
        for step in cast(list[JsonObject], snapshot.content["steps"])
    ]


def task_payload(s: Session, actor: Actor, row: TrainingTask) -> JsonObject:
    access = read_access(s, actor, row.case_id)
    revision = published_snapshot(s, actor, row.revision_id)
    progress = progress_payload(s, actor, row)
    current = next((p["step_id"] for p in progress if p["status"] != "completed"), None)
    return {
        "id": str(row.id),
        "case_id": str(row.case_id),
        "learner_id": str(access.learner_id),
        "title": revision.title,
        "revision": revision.content,
        "status": row.status,
        "due_on": row.due_on.isoformat() if row.due_on else None,
        "current_step_id": current,
        "progress": cast(JsonValue, progress),
        "prompt_override": {"prompt_level": row.prompt_override, "reason": row.prompt_reason}
        if row.prompt_override
        else None,
        "version": row.version,
    }


def list_tasks(
    s: Session,
    actor: Actor,
    limit: int,
    cursor: str | None,
    status: str | None,
    case_id: UUID | None,
) -> tuple[list[JsonObject], str | None]:
    scope = cursor_scope(actor.user_id, "tasks", f"{status or ''}:{case_id or ''}")
    query = select(TrainingTask).where(TrainingTask.case_id.in_(authorized_case_ids(actor)))
    if case_id:
        read_access(s, actor, case_id)
        query = query.where(TrainingTask.case_id == case_id)
    if status:
        query = query.where(TrainingTask.status == status)
    after = decode_cursor(cursor, scope)
    if after:
        query = query.where(tuple_(TrainingTask.created_at, TrainingTask.id) < after)
    rows = list(
        s.scalars(
            query.order_by(TrainingTask.created_at.desc(), TrainingTask.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return [task_payload(s, actor, row) for row in rows], encode_cursor(
        rows[-1].created_at, rows[-1].id, scope
    ) if more else None


def audit(s: Session, actor: Actor, action: str, task_id: UUID, trace_id: str) -> None:
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action=action,
            resource_type="task",
            resource_id=task_id,
            trace_id=trace_id,
        )
    )


def action(
    s: Session, actor: Actor, task_id: UUID, action: str, reason: str, version: str, trace_id: str
) -> JsonObject:
    row, access = task_access(s, actor, task_id, True)
    require_version(version, row.version)
    row.status = transition(actor, access, TaskStatus(row.status), action, reason)
    row.version += 1
    audit(s, actor, "training." + action, task_id, trace_id)
    if action == "cancel":
        append_notifications(s, {access.learner_id}, "training.cancelled", "task", row.id)
    s.flush()
    return task_payload(s, actor, row)


def update_progress(
    s: Session,
    actor: Actor,
    task_id: UUID,
    step_id: UUID,
    status: str,
    attachments: list[UUID],
    version: str,
    trace_id: str,
) -> JsonObject:
    task, access = task_access(s, actor, task_id, True)
    access.require_learner(actor)
    require_version(version, task.version)
    if task.status != "in_progress":
        raise conflict("TASK_NOT_RUNNING")
    progress = s.get(StepProgress, (task_id, step_id))
    if progress is None:
        raise not_found()
    revision = published_snapshot(s, actor, task.revision_id)
    step = next(
        (
            step
            for step in cast(list[JsonObject], revision.content["steps"])
            if step["id"] == str(step_id)
        ),
        None,
    )
    assert step is not None
    current = next(
        (p["step_id"] for p in progress_payload(s, actor, task) if p["status"] != "completed"), None
    )
    if current != str(step_id):
        raise conflict("STEP_ORDER")
    require_files(s, attachments, task.case_id, "task_evidence", task_id)
    if status == "completed" and step["evidence_required"] and not attachments:
        raise conflict("EVIDENCE_REQUIRED")
    progress.status = status
    progress.attachment_ids = [str(i) for i in attachments]
    task.version += 1
    audit(s, actor, "training.step_saved", task_id, trace_id)
    s.flush()
    return task_payload(s, actor, task)


def record_events(
    s: Session, actor: Actor, task_id: UUID, events: list[JsonObject]
) -> dict[str, int]:
    task, access = task_access(s, actor, task_id, True)
    access.require_learner(actor)
    if task.status != "in_progress":
        raise conflict("TASK_NOT_RUNNING")
    allowed = {str(p["step_id"]) for p in progress_payload(s, actor, task)}
    accepted = duplicates = 0
    for event in events:
        if str(event["step_id"]) not in allowed:
            raise AppError(422, "INVALID_STEP", "观测步骤无效")
        at = datetime.fromisoformat(str(event["observed_at"]).replace("Z", "+00:00"))
        if at.tzinfo is None:
            raise AppError(422, "INVALID_TIMESTAMP", "观测时间需要时区")
        values = {
            "task_id": task_id,
            "revision_id": task.revision_id,
            "event_id": UUID(str(event["event_id"])),
            "session_id": UUID(str(event["session_id"])),
            "step_id": UUID(str(event["step_id"])),
            "sequence": int(cast(int, event["sequence"])),
            "kind": str(event["kind"]),
            "value": int(cast(int, event["value"])),
            "observed_at": at,
        }
        inserted = s.scalar(
            insert(TaskEvent)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[TaskEvent.event_id])
            .returning(TaskEvent.id)
        )
        if inserted:
            accepted += 1
        else:
            existing = s.scalar(select(TaskEvent).where(TaskEvent.event_id == values["event_id"]))
            assert existing is not None
            if any(getattr(existing, key) != value for key, value in values.items()):
                raise conflict("EVENT_ID_REUSED")
            duplicates += 1
    return {"accepted": accepted, "duplicates": duplicates}


def submission_access(
    s: Session, actor: Actor, submission_id: UUID, lock: bool = False
) -> tuple[Submission, TrainingTask, CaseAccess]:
    row = s.get(Submission, submission_id)
    if row is None:
        raise not_found()
    task, access = task_access(s, actor, row.task_id, lock)
    return row, task, access


def feedback_payload(row: Feedback) -> JsonObject:
    return {
        "id": str(row.id),
        "submission_id": str(row.submission_id),
        "author_id": str(row.author_id),
        "outcome": row.outcome,
        "message": row.message,
        "redo_step_ids": cast(JsonValue, list(row.redo_step_ids)),
        "annotation_ids": cast(JsonValue, list(row.annotation_ids)),
        "tags": cast(JsonValue, list(row.tags)),
        "created_at": row.created_at.isoformat(),
    }


def submission_payload(s: Session, row: Submission, task: TrainingTask) -> JsonObject:
    feedback = s.scalar(select(Feedback).where(Feedback.submission_id == row.id))
    return {
        "id": str(row.id),
        "task_id": str(row.task_id),
        "attempt_no": row.attempt_no,
        "revision_id": str(task.revision_id),
        "note": row.note,
        "snapshot": row.snapshot,
        "submitted_at": row.created_at.isoformat(),
        "task_version": task.version,
        "task_status": task.status,
        "feedback": feedback_payload(feedback) if feedback else None,
    }


def submissions(
    s: Session, actor: Actor, task_id: UUID, limit: int, cursor: str | None
) -> tuple[list[JsonObject], str | None]:
    task, _ = task_access(s, actor, task_id)
    scope = cursor_scope(actor.user_id, "submissions", str(task_id))
    query = select(Submission).where(Submission.task_id == task_id)
    after = decode_cursor(cursor, scope)
    if after:
        query = query.where(tuple_(Submission.created_at, Submission.id) < after)
    rows = list(
        s.scalars(
            query.order_by(Submission.created_at.desc(), Submission.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return [submission_payload(s, row, task) for row in rows], encode_cursor(
        rows[-1].created_at, rows[-1].id, scope
    ) if more else None


def submit(
    s: Session, actor: Actor, task_id: UUID, note: str, version: str, trace_id: str
) -> JsonObject:
    task, access = task_access(s, actor, task_id, True)
    require_version(version, task.version)
    progress = progress_payload(s, actor, task)
    if not progress or any(p["status"] != "completed" for p in progress):
        raise conflict("INCOMPLETE_STEPS")
    task.status = transition(actor, access, TaskStatus(task.status), "submit")
    snapshot: JsonObject = {
        "schema_version": 1,
        "revision_id": str(task.revision_id),
        "progress": cast(JsonValue, progress),
    }
    attempt = (
        s.scalar(select(func.max(Submission.attempt_no)).where(Submission.task_id == task_id)) or 0
    ) + 1
    row = Submission(task_id=task_id, attempt_no=attempt, note=note, snapshot=snapshot)
    s.add(row)
    task.version += 1
    s.flush()
    ids = [UUID(str(i)) for p in progress for i in cast(list[str], p["attachment_ids"])]
    require_files(s, list(dict.fromkeys(ids)), task.case_id, "task_evidence", task_id)
    link_files(s, list(dict.fromkeys(ids)), task.case_id, "submission", row.id)
    audit(s, actor, "training.submitted", task_id, trace_id)
    append_notifications(s, set(access.counselor_ids), "training.submitted", "submission", row.id)
    s.flush()
    return submission_payload(s, row, task)


def set_prompt_override(
    s: Session, actor: Actor, task_id: UUID, level: int, reason: str, version: str, trace_id: str
) -> JsonObject:
    row, access = task_access(s, actor, task_id, True)
    access.require_counselor(actor)
    require_version(version, row.version)
    if row.status in {"completed", "cancelled"}:
        raise conflict()
    if not reason.strip():
        raise AppError(422, "REASON_REQUIRED", "请填写调整说明")
    row.prompt_override = level
    row.prompt_reason = reason.strip()
    row.version += 1
    audit(s, actor, "training.prompt_override", task_id, trace_id)
    s.flush()
    return task_payload(s, actor, row)


def review(
    s: Session,
    actor: Actor,
    submission_id: UUID,
    body: JsonObject,
    version: str,
    trace_id: str,
    annotations_validated: bool = False,
) -> JsonObject:
    row, task, access = submission_access(s, actor, submission_id, True)
    access.require_counselor(actor)
    require_version(version, task.version)
    if s.scalar(select(Feedback.id).where(Feedback.submission_id == submission_id)):
        raise conflict("FEEDBACK_EXISTS")
    latest = s.scalar(select(func.max(Submission.attempt_no)).where(Submission.task_id == task.id))
    if row.attempt_no != latest:
        raise conflict("STALE_SUBMISSION")
    redo = tuple(UUID(str(i)) for i in cast(list[str], body["redo_step_ids"]))
    step_ids = frozenset(
        UUID(str(p["step_id"])) for p in cast(list[JsonObject], row.snapshot["progress"])
    )
    outcome = str(body["outcome"])
    validate_feedback(outcome, str(body["message"]), redo, step_ids)
    if body["annotation_ids"] and not annotations_validated:
        raise AppError(422, "INVALID_ANNOTATION", "标注尚未核验")
    target = "pass" if outcome == "passed" else "request_changes"
    task.status = transition(actor, access, TaskStatus(task.status), target)
    feedback = Feedback(
        submission_id=submission_id,
        author_id=actor.user_id,
        outcome=outcome,
        message=str(body["message"]),
        redo_step_ids=[str(i) for i in redo],
        annotation_ids=cast(list[str], body["annotation_ids"]),
        tags=cast(list[str], body["tags"]),
    )
    s.add(feedback)
    for step_id in redo:
        progress = s.get(StepProgress, (task.id, step_id))
        assert progress is not None
        progress.status = "pending"
        progress.attachment_ids = []
    task.version += 1
    audit(s, actor, "training.reviewed", task.id, trace_id)
    append_notifications(s, {access.learner_id}, "training.feedback", "task", task.id)
    s.flush()
    return {"feedback": feedback_payload(feedback), "task": task_payload(s, actor, task)}


def records(
    s: Session, actor: Actor, case_id: UUID, limit: int, cursor: str | None
) -> tuple[list[JsonObject], str | None]:
    tasks, cursor = list_tasks(s, actor, limit, cursor, None, case_id)
    result: list[JsonObject] = []
    for task in tasks:
        task_id = UUID(str(task["id"]))
        attempts = (
            s.scalar(
                select(func.count()).select_from(Submission).where(Submission.task_id == task_id)
            )
            or 0
        )
        hints = (
            s.scalar(
                select(func.count())
                .select_from(TaskEvent)
                .where(TaskEvent.task_id == task_id, TaskEvent.kind == "hint_requested")
            )
            or 0
        )
        duration = s.scalar(
            select(func.sum(TaskEvent.value)).where(
                TaskEvent.task_id == task_id, TaskEvent.kind == "time_sample"
            )
        )
        result.append(
            {
                "task_id": str(task_id),
                "title": task["title"],
                "status": task["status"],
                "attempts": attempts,
                "hint_requests": hints,
                "assistance_requests": 0,
                "observed_elapsed_ms": min(duration, 2147483647) if duration is not None else None,
                "measurement_note": "时长来自主动上报的样本；提示与求助次数仅记录事实，不用于能力评分。",
            }
        )
    return result, cursor
