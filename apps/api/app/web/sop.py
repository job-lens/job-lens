from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.modules.cases.queries import read_access
from app.modules.sop import service
from app.modules.sop.queries import revision_payload
from app.modules.training.service import create_for_publication
from app.web.business_schemas import (
    PlanCreate,
    PlanPage,
    Publication,
    PublishRequest,
    RevisionCreate,
    RevisionWrite,
    SopPlan,
    SopRevision,
)
from app.web.commands import READ_RESPONSES, WRITE_RESPONSES, Cursor, Idempotency, Limit, command
from app.web.deps import Authenticated
from app.web.identity import ETAG, Csrf, Version, write_check
from app.web.schemas import AUTHENTICATED_ERRORS, ERROR_RESPONSE

router = APIRouter()
CREATED = {**AUTHENTICATED_ERRORS, 201: {"headers": {"ETag": ETAG}}}


@router.get(
    "/cases/{case_id}/sop-plans",
    operation_id="sop_plans_list",
    response_model=PlanPage,
    responses=AUTHENTICATED_ERRORS,
)
def plans(
    case_id: UUID, context: Authenticated, limit: Limit = 20, cursor: Cursor = None
) -> PlanPage:
    s, actor = context
    rows, cursor = service.list_plans(s, actor, case_id, limit, cursor)
    return PlanPage(
        items=[SopPlan.model_validate(row) for row in rows],
        next_cursor=cursor,
        has_more=cursor is not None,
    )


@router.post(
    "/cases/{case_id}/sop-plans",
    operation_id="sop_plans_create",
    response_model=SopPlan,
    status_code=201,
    responses=CREATED,
)
def create(
    case_id: UUID,
    body: PlanCreate,
    context: Authenticated,
    csrf: Csrf,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        read_access(s, actor, case_id, lock=True).require_counselor(actor)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json"),
        None,
        authorize,
        lambda: SopPlan.model_validate(
            service.create_plan(s, actor, case_id, body.title, request.state.trace_id)
        ),
        status=201,
        etag="version",
    )


@router.get(
    "/sop-plans/{plan_id}",
    operation_id="sop_plans_get",
    response_model=SopPlan,
    responses=READ_RESPONSES,
)
def plan(plan_id: UUID, context: Authenticated, response: Response) -> SopPlan:
    s, actor = context
    row, _ = service.plan_access(s, actor, plan_id)
    result = SopPlan.model_validate(service.plan_payload(s, actor, row))
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.post(
    "/sop-plans/{plan_id}/revisions",
    operation_id="sop_revisions_create",
    response_model=SopRevision,
    status_code=201,
    responses=CREATED,
)
def draft(
    plan_id: UUID,
    body: RevisionCreate,
    context: Authenticated,
    csrf: Csrf,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        _, access = service.plan_access(s, actor, plan_id, True)
        access.require_counselor(actor)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json", exclude_unset=True),
        None,
        authorize,
        lambda: SopRevision.model_validate(
            service.create_revision(
                s, actor, plan_id, body.base_revision_id, request.state.trace_id
            )
        ),
        status=201,
        etag="version",
    )


@router.get(
    "/sop-revisions/{revision_id}",
    operation_id="sop_revisions_get",
    response_model=SopRevision,
    responses=READ_RESPONSES,
)
def revision(revision_id: UUID, context: Authenticated, response: Response) -> SopRevision:
    s, actor = context
    row, _ = service.revision_access(s, actor, revision_id)
    result = SopRevision.model_validate(revision_payload(s, row))
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.put(
    "/sop-revisions/{revision_id}",
    operation_id="sop_revisions_put",
    response_model=SopRevision,
    responses=WRITE_RESPONSES,
)
def save(
    revision_id: UUID,
    body: RevisionWrite,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> SopRevision:
    s, actor = context
    write_check(request, s, csrf)
    result = SopRevision.model_validate(
        service.save_revision(
            s, actor, revision_id, body.model_dump(mode="json"), version, request.state.trace_id
        )
    )
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.post(
    "/sop-revisions/{revision_id}/publish",
    operation_id="sop_publish",
    response_model=Publication,
    responses={**AUTHENTICATED_ERRORS, 412: ERROR_RESPONSE, 428: ERROR_RESPONSE},
)
def publish(
    revision_id: UUID,
    body: PublishRequest,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        _, access = service.revision_access(s, actor, revision_id, True)
        access.require_counselor(actor)

    def apply() -> Publication:
        revision = service.publish(s, actor, revision_id, version, request.state.trace_id)
        task = create_for_publication(s, actor, revision_id, body.due_on, request.state.trace_id)
        return Publication.model_validate(
            {
                "revision_id": revision_id,
                "task_id": task.id,
                "published_at": revision["published_at"],
            }
        )

    return command(
        request, s, actor, csrf, key, body.model_dump(mode="json"), version, authorize, apply
    )
