from collections.abc import Callable
from typing import BinaryIO
from uuid import UUID

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, conflict, forbidden, not_found
from app.core.http import require_version
from app.core.types import JsonObject
from app.infrastructure.file_jobs import inspect_file
from app.infrastructure.jobs import enqueue
from app.infrastructure.models import AuditEvent, FileAsset, FileLink
from app.infrastructure.storage import BlobStore

# Callback authorizes the parent and reports whether the caller is its learner.
# Infrastructure never imports case or task ORM models.
type AuthorizeCase = Callable[[UUID], bool]


def get(s: Session, actor_id: UUID, identifier: UUID, authorize: AuthorizeCase) -> FileAsset:
    case_id = s.scalar(select(FileAsset.case_id).where(FileAsset.id == identifier))
    if case_id is None:
        raise not_found()
    learner = authorize(case_id)
    row = s.scalar(
        select(FileAsset)
        .where(FileAsset.id == identifier)
        .execution_options(populate_existing=True)
    )
    if row is None or row.state == "deleted":
        raise not_found()
    if row.uploader_id != actor_id:
        if row.state != "ready":
            raise not_found()
        if (
            learner
            and row.purpose == "sop_media"
            and not s.scalar(
                select(FileLink.id).where(
                    FileLink.asset_id == identifier, FileLink.owner_kind == "sop_revision"
                )
            )
        ):
            raise not_found()
    return row


def payload(row: FileAsset) -> JsonObject:
    return dict(
        id=str(row.id),
        case_id=str(row.case_id),
        task_id=str(row.task_id) if row.task_id else None,
        purpose=row.purpose,
        filename=row.filename,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        state=row.state,
        reason=row.reason,
        width=row.width,
        height=row.height,
        version=row.version,
        created_at=row.created_at.isoformat(),
    )


def upload(
    s: Session,
    actor_id: UUID,
    case_id: UUID,
    task_id: UUID | None,
    purpose: str,
    filename: str,
    source: BinaryIO,
    store: BlobStore,
    trace_id: str,
) -> FileAsset:
    try:
        stored = store.put(source, 20 * 1024 * 1024)
    except ValueError:
        raise AppError(413, "FILE_SIZE_INVALID", "文件需为 1 字节至 20 MB") from None
    try:
        mime, width, height = inspect_file(store, stored.key)
        row = FileAsset(
            case_id=case_id,
            task_id=task_id,
            uploader_id=actor_id,
            purpose=purpose,
            storage_key=stored.key,
            filename=filename,
            mime_type=mime,
            size_bytes=stored.size,
            sha256=stored.sha256,
            width=width,
            height=height,
        )
        s.add(row)
        # If the request transaction fails after the insert, do not leave a blob.
        event.listen(s, "after_rollback", lambda session: store.delete(stored.key), once=True)
        s.flush()
        s.add(
            AuditEvent(
                actor_id=actor_id,
                action="files.uploaded",
                resource_type="file",
                resource_id=row.id,
                trace_id=trace_id,
            )
        )
        enqueue(s, "files.scan", {"asset_id": str(row.id)}, "files.scan:" + str(row.id))
        return row
    except BaseException:
        store.delete(stored.key)
        raise


def delete(
    s: Session,
    actor_id: UUID,
    identifier: UUID,
    version: str,
    authorize: AuthorizeCase,
    trace_id: str,
) -> None:
    row = get(s, actor_id, identifier, authorize)
    if row.uploader_id != actor_id:
        raise forbidden()
    s.refresh(row, with_for_update=True)
    require_version(version, row.version)
    if row.state == "deleted":
        raise not_found()
    if s.scalar(select(FileLink.id).where(FileLink.asset_id == identifier)):
        raise conflict("FILE_IN_USE")
    row.state = "deleted"
    row.version += 1
    s.add(
        AuditEvent(
            actor_id=actor_id,
            action="files.deleted",
            resource_type="file",
            resource_id=row.id,
            trace_id=trace_id,
        )
    )
    enqueue(s, "files.delete", {"asset_id": str(row.id)}, "files.delete:" + str(row.id))
