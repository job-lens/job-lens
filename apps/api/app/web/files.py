import hashlib
from collections.abc import Iterator
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import StreamingResponse

from app.core.errors import AppError, conflict, not_found
from app.core.types import JsonObject
from app.infrastructure import file_service as service
from app.infrastructure.idempotency import CommandResult, Scope, execute_once, fingerprint
from app.infrastructure.storage import BlobStore, LocalBlobStore, S3BlobStore
from app.modules.cases.queries import read_access
from app.modules.training.queries import task_context
from app.web.business_schemas import FileAsset, FileUpload
from app.web.commands import READ_RESPONSES, Idempotency
from app.web.deps import Authenticated
from app.web.identity import Csrf, Version, write_check
from app.web.schemas import AUTHENTICATED_ERRORS, ERROR_RESPONSE

router = APIRouter()


def store(request: Request) -> BlobStore:
    settings = request.app.state.settings
    return (
        LocalBlobStore(settings.storage_root)
        if settings.storage_kind == "local"
        else S3BlobStore(settings)
    )


@router.post(
    "/files",
    operation_id="files_upload",
    status_code=202,
    response_model=FileAsset,
    responses={**AUTHENTICATED_ERRORS, 413: ERROR_RESPONSE, 415: ERROR_RESPONSE},
)
def upload(
    body: Annotated[FileUpload, Form(media_type="multipart/form-data")],
    context: Authenticated,
    csrf: Csrf,
    key: Idempotency,
    request: Request,
) -> FileAsset:
    s, actor = context
    write_check(request, s, csrf)

    def authorize() -> None:
        access = read_access(s, actor, body.case_id, lock=True)
        if body.purpose == "sop_media":
            access.require_counselor(actor)
        elif body.purpose in {"profile_material", "task_evidence"}:
            access.require_learner(actor)

    authorize()
    if body.task_id:
        case_id, _, status, _ = task_context(s, actor, body.task_id)
        if case_id != body.case_id:
            raise not_found()
        if body.purpose == "task_evidence" and status != "in_progress":
            raise conflict()
    elif body.purpose == "task_evidence":
        raise AppError(422, "TASK_REQUIRED", "训练证据需要对应任务")
    if body.purpose in {"profile_material", "sop_media"} and body.task_id:
        raise AppError(422, "INVALID_FILE_CONTEXT", "此类文件不关联任务")
    if not request.app.state.settings.scan_enabled:
        # Authentication/authorization remain mandatory. Do not create a private
        # blob, asset, job, or successful idempotency result while scanning is off.
        raise AppError(503, "SCAN_UNAVAILABLE", "文件检测暂不可用，上传暂不可用")
    filename = (body.file.filename or "文件").replace("\\", "/").rsplit("/", 1)[-1]
    if (
        not filename.strip()
        or len(filename) > 255
        or any(ord(c) < 32 or ord(c) == 127 for c in filename)
    ):
        raise AppError(422, "INVALID_FILENAME", "文件名无效")
    # Fingerprint the bounded stream before replay, without a second persisted blob.
    size, digest = 0, hashlib.sha256()
    while chunk := body.file.file.read(64 * 1024):
        size += len(chunk)
        if size > 20 * 1024 * 1024:
            raise AppError(413, "FILE_SIZE_INVALID", "文件不能超过 20 MB")
        digest.update(chunk)
    if not size:
        raise AppError(413, "FILE_SIZE_INVALID", "请选择非空文件")
    body.file.file.seek(0)
    identity: JsonObject = dict(
        case_id=str(body.case_id),
        task_id=str(body.task_id) if body.task_id else None,
        purpose=body.purpose,
        filename=filename,
        sha256=digest.hexdigest(),
        size=size,
    )
    blob = store(request)

    def apply() -> CommandResult:
        row = service.upload(
            s,
            actor.user_id,
            body.case_id,
            body.task_id,
            body.purpose,
            filename,
            body.file.file,
            blob,
            request.state.trace_id,
        )
        return CommandResult(202, service.payload(row), {})

    result = execute_once(
        s,
        Scope(actor.user_id, request.method, request.url.path, key),
        fingerprint(identity),
        authorize,
        apply,
    )
    return FileAsset.model_validate(result.body)


@router.get(
    "/files/{file_id}", operation_id="files_get", response_model=FileAsset, responses=READ_RESPONSES
)
def metadata(file_id: UUID, context: Authenticated, response: Response) -> FileAsset:
    s, actor = context

    def authorize(case_id: UUID) -> bool:
        return read_access(s, actor, case_id).learner_id == actor.user_id

    row = service.get(s, actor.user_id, file_id, authorize)
    response.headers["ETag"] = f'"{row.version}"'
    return FileAsset.model_validate(row)


@router.delete(
    "/files/{file_id}",
    operation_id="files_delete",
    status_code=204,
    responses={
        **AUTHENTICATED_ERRORS,
        409: ERROR_RESPONSE,
        412: ERROR_RESPONSE,
        428: ERROR_RESPONSE,
    },
)
def delete(
    file_id: UUID, context: Authenticated, csrf: Csrf, version: Version, request: Request
) -> Response:
    s, actor = context
    write_check(request, s, csrf)

    def authorize(case_id: UUID) -> bool:
        return read_access(s, actor, case_id, lock=True).learner_id == actor.user_id

    service.delete(s, actor.user_id, file_id, version, authorize, request.state.trace_id)
    return Response(status_code=204)


@router.get(
    "/files/{file_id}/content",
    operation_id="files_content",
    response_class=StreamingResponse,
    responses={
        **AUTHENTICATED_ERRORS,
        200: {
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            }
        },
        409: ERROR_RESPONSE,
    },
)
def content(file_id: UUID, context: Authenticated, request: Request) -> StreamingResponse:
    s, actor = context

    def authorize(case_id: UUID) -> bool:
        return read_access(s, actor, case_id).learner_id == actor.user_id

    row = service.get(s, actor.user_id, file_id, authorize)
    if row.state != "ready":
        raise conflict("FILE_NOT_READY")
    blob, key = store(request), row.storage_key

    def chunks() -> Iterator[bytes]:
        with blob.open(key) as source:
            while chunk := source.read(64 * 1024):
                yield chunk

    disposition = "inline" if row.mime_type.startswith("image/") else "attachment"
    return StreamingResponse(
        chunks(),
        media_type=row.mime_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(row.filename, safe='')}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
