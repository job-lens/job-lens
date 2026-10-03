from typing import cast
from uuid import UUID

from sqlalchemy import or_, select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import AppError, conflict, forbidden, not_found
from app.core.http import require_version
from app.core.types import Actor, JsonObject, JsonValue
from app.infrastructure.assets import link_files, require_files
from app.infrastructure.models import AuditEvent, FileAsset
from app.infrastructure.notifications import append_notifications
from app.infrastructure.pagination import cursor_scope, decode_cursor, encode_cursor
from app.modules.cases.public import CaseAccess
from app.modules.cases.queries import authorized_case_ids, read_access
from app.modules.support.models import Annotation, Assistance, SupportMessage
from app.modules.support.public import Marker
from app.modules.support.rules import AssistanceState, transition_assistance
from app.modules.training.queries import submission_context, task_context


def audit(s: Session, actor: Actor, kind: str, row: Assistance | Annotation, trace: str) -> None:
    s.add(
        AuditEvent(
            actor_id=actor.user_id,
            action=kind,
            resource_type="assistance" if isinstance(row, Assistance) else "annotation",
            resource_id=row.id,
            trace_id=trace,
        )
    )


def recipients(access: CaseAccess, actor: Actor) -> set[UUID]:
    return (set(access.counselor_ids) | {access.learner_id}) - {actor.user_id}


def assistance_access(
    s: Session, actor: Actor, identifier: UUID, lock: bool = False
) -> tuple[Assistance, CaseAccess]:
    case_id = s.scalar(select(Assistance.case_id).where(Assistance.id == identifier))
    if case_id is None:
        raise not_found()
    access = read_access(s, actor, case_id, lock=lock)
    row = s.scalar(
        select(Assistance)
        .where(Assistance.id == identifier)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise not_found()
    return row, access


def assistance_payload(row: Assistance, access: CaseAccess) -> JsonObject:
    if not access.counselor_ids:
        raise conflict("NO_ASSIGNED_COUNSELOR")
    return dict(
        id=str(row.id),
        case_id=str(row.case_id),
        task_id=str(row.task_id) if row.task_id else None,
        step_id=str(row.step_id) if row.step_id else None,
        message=row.message,
        attachment_ids=cast(list[JsonValue], row.attachment_ids),
        preferred_mode=row.preferred_mode,
        counselor_id=str(sorted(access.counselor_ids)[0]) if access.counselor_ids else None,
        state=row.state,
        version=row.version,
        created_at=row.created_at.isoformat(),
    )


def create_assistance(s: Session, actor: Actor, body: JsonObject, trace: str) -> JsonObject:
    case_id = UUID(str(body["case_id"]))
    access = read_access(s, actor, case_id, lock=True)
    access.require_learner(actor)
    if not access.counselor_ids:
        raise conflict("NO_ASSIGNED_COUNSELOR")
    task_id = UUID(str(body["task_id"])) if body["task_id"] else None
    step_id = UUID(str(body["step_id"])) if body["step_id"] else None
    revision_id = None
    if task_id:
        task_case, revision_id, status, steps = task_context(s, actor, task_id)
        if task_case != case_id or (step_id and step_id not in steps):
            raise not_found()
        if status in {"completed", "cancelled"}:
            raise conflict()
    elif step_id:
        raise AppError(422, "STEP_CONTEXT_REQUIRED", "步骤需要对应任务")
    if not str(body["message"]).strip():
        raise AppError(422, "MESSAGE_REQUIRED", "请填写需要帮助的内容")
    if s.scalar(
        select(Assistance.id).where(
            Assistance.case_id == case_id,
            Assistance.task_id == task_id,
            Assistance.state.in_(["queued", "accepted"]),
        )
    ):
        raise conflict("OPEN_ASSISTANCE_EXISTS")
    ids = [UUID(str(i)) for i in cast(list[JsonValue], body["attachment_ids"])]
    require_files(s, ids, case_id, "support_message", task_id)
    row = Assistance(
        case_id=case_id,
        task_id=task_id,
        step_id=step_id,
        revision_id=revision_id,
        message=str(body["message"]).strip(),
        attachment_ids=[str(i) for i in ids],
        preferred_mode=str(body["preferred_mode"]),
    )
    s.add(row)
    s.flush()
    link_files(s, ids, case_id, "support_message", row.id)
    audit(s, actor, "support.requested", row, trace)
    append_notifications(s, set(access.counselor_ids), "support.requested", "assistance", row.id)
    return assistance_payload(row, access)


def change_assistance(
    s: Session, actor: Actor, identifier: UUID, action: str, note: str, version: str, trace: str
) -> JsonObject:
    row, access = assistance_access(s, actor, identifier, True)
    require_version(version, row.version)
    row.state = transition_assistance(actor, access, cast(AssistanceState, row.state), action)
    row.version += 1
    if note.strip():
        s.add(
            SupportMessage(
                request_id=row.id, author_id=actor.user_id, body=note.strip(), attachment_ids=[]
            )
        )
    audit(s, actor, "support." + action, row, trace)
    append_notifications(s, recipients(access, actor), "support." + action, "assistance", row.id)
    s.flush()
    return assistance_payload(row, access)


def add_message(
    s: Session, actor: Actor, identifier: UUID, text: str, ids: list[UUID], trace: str
) -> SupportMessage:
    row, access = assistance_access(s, actor, identifier, True)
    if row.state not in {"queued", "accepted"}:
        raise conflict()
    if not text.strip() and not ids:
        raise AppError(422, "MESSAGE_REQUIRED", "请填写消息或选择附件")
    require_files(s, ids, row.case_id, "support_message", row.task_id)
    message = SupportMessage(
        request_id=row.id,
        author_id=actor.user_id,
        body=text.strip(),
        attachment_ids=[str(i) for i in ids],
    )
    s.add(message)
    s.flush()
    link_files(s, ids, row.case_id, "support_message", message.id)
    audit(s, actor, "support.message", row, trace)
    append_notifications(s, recipients(access, actor), "support.message", "assistance", row.id)
    return message


def list_assistance(
    s: Session,
    actor: Actor,
    limit: int,
    cursor: str | None,
    state: str | None,
    case_id: UUID | None,
) -> tuple[list[JsonObject], str | None]:
    if case_id:
        read_access(s, actor, case_id)
    scope = cursor_scope(actor.user_id, "assistance", f"{state}:{case_id}")
    query = select(Assistance).where(Assistance.case_id.in_(authorized_case_ids(actor)))
    if state:
        query = query.where(Assistance.state == state)
    if case_id:
        query = query.where(Assistance.case_id == case_id)
    position = decode_cursor(cursor, scope)
    if position:
        query = query.where(tuple_(Assistance.created_at, Assistance.id) < position)
    rows = list(
        s.scalars(
            query.order_by(Assistance.created_at.desc(), Assistance.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return [
        assistance_payload(row, read_access(s, actor, row.case_id)) for row in rows
    ], encode_cursor(rows[-1].created_at, rows[-1].id, scope) if more else None


def list_messages(
    s: Session, actor: Actor, identifier: UUID, limit: int, cursor: str | None
) -> tuple[list[SupportMessage], str | None]:
    assistance_access(s, actor, identifier)
    scope = cursor_scope(actor.user_id, "messages", str(identifier))
    query = select(SupportMessage).where(SupportMessage.request_id == identifier)
    position = decode_cursor(cursor, scope)
    if position:
        query = query.where(tuple_(SupportMessage.created_at, SupportMessage.id) < position)
    rows = list(
        s.scalars(
            query.order_by(SupportMessage.created_at.desc(), SupportMessage.id.desc()).limit(
                limit + 1
            )
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, encode_cursor(rows[-1].created_at, rows[-1].id, scope) if more else None


def validate_markers(markers: list[JsonObject]) -> None:
    if len({str(m["id"]) for m in markers}) != len(markers):
        raise AppError(422, "INVALID_GEOMETRY", "标注编号不能重复")
    for marker in markers:
        try:
            Marker(
                float(cast(float, marker["x"])),
                float(cast(float, marker["y"])),
                str(marker["text"]),
                float(cast(float, marker["width"])) if marker["shape"] == "rect" else None,
                float(cast(float, marker["height"])) if marker["shape"] == "rect" else None,
            ).validate()
        except ValueError:
            raise AppError(422, "INVALID_GEOMETRY", "请检查标注范围与文字") from None


def annotation_access(
    s: Session, actor: Actor, identifier: UUID, lock: bool = False, author: bool = False
) -> tuple[Annotation, CaseAccess]:
    case_id = s.scalar(select(Annotation.case_id).where(Annotation.id == identifier))
    if case_id is None:
        raise not_found()
    access = read_access(s, actor, case_id, lock=lock)
    row = s.scalar(
        select(Annotation)
        .where(Annotation.id == identifier)
        .execution_options(populate_existing=True)
    )
    if row is None or (row.state == "draft" and row.author_id != actor.user_id):
        raise not_found()
    if author and row.author_id != actor.user_id:
        raise forbidden()
    return row, access


def create_annotation(
    s: Session, actor: Actor, task_id: UUID, body: JsonObject, trace: str
) -> Annotation:
    case_id, _, _, _ = task_context(s, actor, task_id)
    access = read_access(s, actor, case_id, lock=True)
    if body["kind"] == "question":
        access.require_learner(actor)
    else:
        access.require_counselor(actor)
    asset_id = UUID(str(body["asset_id"]))
    assets = require_files(s, [asset_id], case_id, "task_evidence", task_id)
    if not assets[0].width or not assets[0].height or not assets[0].mime_type.startswith("image/"):
        raise AppError(422, "IMAGE_REQUIRED", "只能标注已检查的图片")
    submission_id = UUID(str(body["submission_id"])) if body["submission_id"] else None
    if body["kind"] == "guidance" and not submission_id:
        raise AppError(422, "SUBMISSION_REQUIRED", "指引需要对应提交")
    if submission_id:
        parent, snapshot = submission_context(s, actor, submission_id)
        ids = {
            str(i)
            for progress in cast(list[JsonObject], snapshot["progress"])
            for i in cast(list[JsonValue], progress["attachment_ids"])
        }
        if parent != task_id or str(asset_id) not in ids:
            raise not_found()
    markers = cast(list[JsonObject], body["markers"])
    validate_markers(markers)
    row = Annotation(
        case_id=case_id,
        task_id=task_id,
        asset_id=asset_id,
        submission_id=submission_id,
        author_id=actor.user_id,
        kind=str(body["kind"]),
        markers=markers,
    )
    s.add(row)
    s.flush()
    link_files(s, [asset_id], case_id, "annotation", row.id)
    audit(s, actor, "support.annotation_created", row, trace)
    return row


def save_annotation(
    s: Session, actor: Actor, identifier: UUID, markers: list[JsonObject], version: str, trace: str
) -> Annotation:
    row, _ = annotation_access(s, actor, identifier, True, True)
    require_version(version, row.version)
    if row.state != "draft":
        raise conflict("IMMUTABLE_ANNOTATION")
    validate_markers(markers)
    row.markers = markers
    row.version += 1
    audit(s, actor, "support.annotation_saved", row, trace)
    s.flush()
    return row


def publish_annotation(
    s: Session, actor: Actor, identifier: UUID, version: str, trace: str
) -> Annotation:
    row, access = annotation_access(s, actor, identifier, True, True)
    require_version(version, row.version)
    if row.state != "draft":
        raise conflict("IMMUTABLE_ANNOTATION")
    validate_markers(row.markers)
    asset = s.get(FileAsset, row.asset_id)
    if asset is None or asset.state != "ready":
        raise conflict("FILE_NOT_READY")
    row.state = "published"
    row.version += 1
    audit(s, actor, "support.annotation_published", row, trace)
    append_notifications(
        s, recipients(access, actor), "support.annotation_published", "annotation", row.id
    )
    s.flush()
    return row


def list_annotations(
    s: Session, actor: Actor, task_id: UUID, limit: int, cursor: str | None
) -> tuple[list[Annotation], str | None]:
    task_context(s, actor, task_id)
    scope = cursor_scope(actor.user_id, "annotations", str(task_id))
    query = select(Annotation).where(
        Annotation.task_id == task_id,
        or_(Annotation.state == "published", Annotation.author_id == actor.user_id),
    )
    position = decode_cursor(cursor, scope)
    if position:
        query = query.where(tuple_(Annotation.created_at, Annotation.id) < position)
    rows = list(
        s.scalars(
            query.order_by(Annotation.created_at.desc(), Annotation.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, encode_cursor(rows[-1].created_at, rows[-1].id, scope) if more else None


def feedback_annotations(
    s: Session, actor: Actor, submission_id: UUID, ids: list[UUID], trace: str
) -> None:
    if len(set(ids)) != len(ids):
        raise conflict("DUPLICATE_ANNOTATION")
    task_id, _ = submission_context(s, actor, submission_id)
    for identifier in sorted(ids):
        row, access = annotation_access(s, actor, identifier, True, True)
        access.require_counselor(actor)
        if row.task_id != task_id or row.submission_id != submission_id or row.kind != "guidance":
            raise not_found()
        if row.state == "draft":
            publish_annotation(s, actor, identifier, f'"{row.version}"', trace)
