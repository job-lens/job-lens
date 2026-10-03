from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import WithJsonSchema

from app.core.errors import forbidden
from app.core.types import Actor
from app.infrastructure.db import utcnow
from app.modules.cases import service
from app.modules.cases.queries import read_access
from app.modules.support.queries import pending_count
from app.modules.training.queries import current_tasks, workload_counts
from app.web.business_schemas import (
    Case,
    CasePage,
    CaseProfile,
    Dashboard,
    FileAsset,
    FilePage,
    MatchWrite,
    SupportMatch,
)
from app.web.commands import READ_RESPONSES, WRITE_RESPONSES, Cursor, Idempotency, Limit, command
from app.web.deps import Authenticated
from app.web.identity import Csrf, Version, write_check
from app.web.schemas import AUTHENTICATED_ERRORS

router = APIRouter()


def project(raw: dict[str, object], task: tuple[UUID, str] | None) -> Case:
    lifecycle = raw["lifecycle"]
    status = (
        "closed"
        if lifecycle == "closed"
        else "pending_match"
        if lifecycle == "pending_match"
        else "sop_pending"
    )
    if task and lifecycle != "closed":
        status = {
            "submitted": "awaiting_feedback",
            "changes_requested": "feedback_available",
            "completed": "stage_complete",
            "cancelled": "sop_pending",
        }.get(task[1], "training")
    return Case.model_validate(
        {**raw, "display_status": status, "current_task_id": task[0] if task else None}
    )


@router.get(
    "/dashboard",
    operation_id="cases_dashboard",
    response_model=Dashboard,
    responses=AUTHENTICATED_ERRORS,
)
def dashboard(context: Authenticated, view: Literal["learner", "counselor"]) -> Dashboard:
    s, actor = context
    if view not in actor.roles:
        raise forbidden()
    scoped = Actor(actor.user_id, frozenset({view}))
    pending, feedback = workload_counts(s, scoped)
    return Dashboard(
        view=view,
        pending_tasks=pending,
        pending_feedback=feedback,
        pending_assistance=pending_count(s, scoped),
        as_of=utcnow(),
    )


@router.get(
    "/cases", operation_id="cases_list", response_model=CasePage, responses=AUTHENTICATED_ERRORS
)
def cases(
    context: Authenticated,
    limit: Limit = 20,
    cursor: Cursor = None,
    state: Annotated[
        Literal["pending_match", "active", "closed"] | None,
        Query(),
        WithJsonSchema({"type": "string", "enum": ["pending_match", "active", "closed"]}),
    ] = None,
) -> CasePage:
    s, actor = context
    items, next_cursor = service.list_cases(s, actor, limit, cursor, state)
    tasks = current_tasks(s, actor, [UUID(str(item["id"])) for item in items])
    return CasePage(
        items=[project(item, tasks.get(UUID(str(item["id"])))) for item in items],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.get(
    "/cases/{case_id}", operation_id="cases_get", response_model=Case, responses=READ_RESPONSES
)
def get(case_id: UUID, context: Authenticated, response: Response) -> Case:
    s, actor = context
    value = project(
        service.get_case(s, actor, case_id), current_tasks(s, actor, [case_id]).get(case_id)
    )
    response.headers["ETag"] = f'"{value.version}"'
    return value


@router.get(
    "/cases/{case_id}/profile",
    operation_id="cases_profile",
    response_model=CaseProfile,
    responses=AUTHENTICATED_ERRORS,
)
def profile(case_id: UUID, context: Authenticated) -> CaseProfile:
    s, actor = context
    return CaseProfile.model_validate(service.get_profile(s, actor, case_id))


@router.get(
    "/cases/{case_id}/materials",
    operation_id="cases_materials",
    response_model=FilePage,
    responses=AUTHENTICATED_ERRORS,
)
def materials(
    case_id: UUID, context: Authenticated, limit: Limit = 20, cursor: Cursor = None
) -> FilePage:
    s, actor = context
    rows, next_cursor = service.materials(s, actor, case_id, limit, cursor)
    return FilePage(
        items=[FileAsset.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.get(
    "/cases/{case_id}/match",
    operation_id="cases_match_get",
    response_model=SupportMatch,
    responses=READ_RESPONSES,
)
def match(case_id: UUID, context: Authenticated, response: Response) -> SupportMatch:
    s, actor = context
    value = SupportMatch.model_validate(service.get_match(s, actor, case_id))
    response.headers["ETag"] = f'"{value.version}"'
    return value


@router.put(
    "/cases/{case_id}/match",
    operation_id="cases_match_put",
    response_model=SupportMatch,
    responses=WRITE_RESPONSES,
)
def save(
    case_id: UUID,
    body: MatchWrite,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> SupportMatch:
    s, actor = context
    write_check(request, s, csrf)
    value = SupportMatch.model_validate(
        service.save_match(s, actor, case_id, body.model_dump(), version, request.state.trace_id)
    )
    response.headers["ETag"] = f'"{value.version}"'
    return value


@router.post(
    "/cases/{case_id}/match/confirm",
    operation_id="cases_match_confirm",
    response_model=SupportMatch,
    responses=WRITE_RESPONSES,
)
def confirm(
    case_id: UUID,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
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
        {},
        version,
        authorize,
        lambda: SupportMatch.model_validate(
            service.confirm_match(s, actor, case_id, version, request.state.trace_id)
        ),
        etag="version",
    )
