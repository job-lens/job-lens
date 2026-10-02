from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import WithJsonSchema

from app.core.types import JsonObject
from app.modules.cases.queries import read_access
from app.modules.support import service
from app.modules.training import service as training
from app.modules.training.queries import task_context
from app.web.business_schemas import (
    Annotation,
    AnnotationCreate,
    AnnotationPage,
    AnnotationWrite,
    Assistance,
    AssistanceAction,
    AssistanceCreate,
    AssistancePage,
    MessageCreate,
    MessagePage,
    PromptOverrideWrite,
    SupportMessage,
    Task,
)
from app.web.commands import READ_RESPONSES, WRITE_RESPONSES, Cursor, Idempotency, Limit, command
from app.web.deps import Authenticated
from app.web.identity import ETAG, Csrf, Version, write_check
from app.web.schemas import AUTHENTICATED_ERRORS, ERROR_RESPONSE

router = APIRouter()
CREATED = {**AUTHENTICATED_ERRORS, 201: {"headers": {"ETag": ETAG}}}
State = Annotated[
    Literal["queued", "accepted", "resolved", "cancelled"] | None,
    Query(),
    WithJsonSchema({"type": "string", "enum": ["queued", "accepted", "resolved", "cancelled"]}),
]
CaseFilter = Annotated[UUID | None, Query(), WithJsonSchema({"type": "string", "format": "uuid"})]


@router.put(
    "/tasks/{task_id}/prompt-override",
    operation_id="support_prompt_override",
    response_model=Task,
    responses=WRITE_RESPONSES,
)
def prompt(
    task_id: UUID,
    body: PromptOverrideWrite,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> Task:
    s, actor = context
    write_check(request, s, csrf)
    result = Task.model_validate(
        training.set_prompt_override(
            s, actor, task_id, body.prompt_level, body.reason, version, request.state.trace_id
        )
    )
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.get(
    "/assistance-requests",
    operation_id="support_requests_list",
    response_model=AssistancePage,
    responses=AUTHENTICATED_ERRORS,
)
def requests(
    context: Authenticated,
    limit: Limit = 20,
    cursor: Cursor = None,
    state: State = None,
    case_id: CaseFilter = None,
) -> AssistancePage:
    s, actor = context
    rows, next_cursor = service.list_assistance(s, actor, limit, cursor, state, case_id)
    return AssistancePage(
        items=[Assistance.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.post(
    "/assistance-requests",
    operation_id="support_requests_create",
    response_model=Assistance,
    status_code=201,
    responses={**CREATED, 409: ERROR_RESPONSE},
)
def create(
    body: AssistanceCreate, context: Authenticated, csrf: Csrf, key: Idempotency, request: Request
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        read_access(s, actor, body.case_id, lock=True).require_learner(actor)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json"),
        None,
        authorize,
        lambda: Assistance.model_validate(
            service.create_assistance(
                s, actor, body.model_dump(mode="json"), request.state.trace_id
            )
        ),
        status=201,
        etag="version",
    )


@router.get(
    "/assistance-requests/{request_id}",
    operation_id="support_requests_get",
    response_model=Assistance,
    responses=READ_RESPONSES,
)
def request_detail(request_id: UUID, context: Authenticated, response: Response) -> Assistance:
    s, actor = context
    row, access = service.assistance_access(s, actor, request_id)
    result = Assistance.model_validate(service.assistance_payload(row, access))
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.post(
    "/assistance-requests/{request_id}/actions",
    operation_id="support_requests_action",
    response_model=Assistance,
    responses=WRITE_RESPONSES,
)
def action(
    request_id: UUID,
    body: AssistanceAction,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        _, access = service.assistance_access(s, actor, request_id, True)
        if body.action == "cancel":
            access.require_learner(actor)
        else:
            access.require_counselor(actor)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json", exclude_unset=True),
        version,
        authorize,
        lambda: Assistance.model_validate(
            service.change_assistance(
                s, actor, request_id, body.action, body.note or "", version, request.state.trace_id
            )
        ),
        etag="version",
    )


@router.get(
    "/assistance-requests/{request_id}/messages",
    operation_id="support_messages_list",
    response_model=MessagePage,
    responses=AUTHENTICATED_ERRORS,
)
def messages(
    request_id: UUID, context: Authenticated, limit: Limit = 20, cursor: Cursor = None
) -> MessagePage:
    s, actor = context
    rows, next_cursor = service.list_messages(s, actor, request_id, limit, cursor)
    return MessagePage(
        items=[SupportMessage.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.post(
    "/assistance-requests/{request_id}/messages",
    operation_id="support_messages_create",
    response_model=SupportMessage,
    status_code=201,
    responses={**AUTHENTICATED_ERRORS, 409: ERROR_RESPONSE},
)
def message(
    request_id: UUID,
    body: MessageCreate,
    context: Authenticated,
    csrf: Csrf,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        service.assistance_access(s, actor, request_id, True)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json"),
        None,
        authorize,
        lambda: SupportMessage.model_validate(
            service.add_message(
                s, actor, request_id, body.body, body.attachment_ids, request.state.trace_id
            )
        ),
        status=201,
    )


@router.get(
    "/tasks/{task_id}/annotations",
    operation_id="support_annotations_list",
    response_model=AnnotationPage,
    responses=AUTHENTICATED_ERRORS,
)
def annotations(
    task_id: UUID, context: Authenticated, limit: Limit = 20, cursor: Cursor = None
) -> AnnotationPage:
    s, actor = context
    rows, next_cursor = service.list_annotations(s, actor, task_id, limit, cursor)
    return AnnotationPage(
        items=[Annotation.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.post(
    "/tasks/{task_id}/annotations",
    operation_id="support_annotations_create",
    response_model=Annotation,
    status_code=201,
    responses=CREATED,
)
def create_annotation(
    task_id: UUID,
    body: AnnotationCreate,
    context: Authenticated,
    csrf: Csrf,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        case_id, _, _, _ = task_context(s, actor, task_id)
        access = read_access(s, actor, case_id, lock=True)
        if body.kind == "question":
            access.require_learner(actor)
        else:
            access.require_counselor(actor)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json"),
        None,
        authorize,
        lambda: Annotation.model_validate(
            service.create_annotation(
                s, actor, task_id, body.model_dump(mode="json"), request.state.trace_id
            )
        ),
        status=201,
        etag="version",
    )


@router.get(
    "/annotations/{annotation_id}",
    operation_id="support_annotations_get",
    response_model=Annotation,
    responses=READ_RESPONSES,
)
def annotation(annotation_id: UUID, context: Authenticated, response: Response) -> Annotation:
    s, actor = context
    row, _ = service.annotation_access(s, actor, annotation_id)
    response.headers["ETag"] = f'"{row.version}"'
    return Annotation.model_validate(row)


@router.put(
    "/annotations/{annotation_id}",
    operation_id="support_annotations_put",
    response_model=Annotation,
    responses=WRITE_RESPONSES,
)
def save_annotation(
    annotation_id: UUID,
    body: AnnotationWrite,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> Annotation:
    s, actor = context
    write_check(request, s, csrf)
    row = service.save_annotation(
        s,
        actor,
        annotation_id,
        cast(list[JsonObject], body.model_dump(mode="json")["markers"]),
        version,
        request.state.trace_id,
    )
    response.headers["ETag"] = f'"{row.version}"'
    return Annotation.model_validate(row)


@router.post(
    "/annotations/{annotation_id}/publish",
    operation_id="support_annotations_publish",
    response_model=Annotation,
    responses=WRITE_RESPONSES,
)
def publish_annotation(
    annotation_id: UUID,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        service.annotation_access(s, actor, annotation_id, True, True)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        {},
        version,
        authorize,
        lambda: Annotation.model_validate(
            service.publish_annotation(s, actor, annotation_id, version, request.state.trace_id)
        ),
        etag="version",
    )
