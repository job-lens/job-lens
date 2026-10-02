from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import WithJsonSchema

from app.modules.support import service as support
from app.modules.support.queries import request_counts
from app.modules.training import service
from app.web.business_schemas import (
    EventBatch,
    EventReceipt,
    FeedbackCreate,
    FeedbackResult,
    ProgressWrite,
    RecordPage,
    Submission,
    SubmissionCreate,
    SubmissionPage,
    Task,
    TaskAction,
    TaskPage,
    TrainingRecord,
)
from app.web.commands import READ_RESPONSES, WRITE_RESPONSES, Cursor, Idempotency, Limit, command
from app.web.deps import Authenticated
from app.web.identity import ETAG, Csrf, Version, write_check
from app.web.schemas import AUTHENTICATED_ERRORS, ERROR_RESPONSE

router = APIRouter()
CREATED = {
    **AUTHENTICATED_ERRORS,
    201: {"headers": {"ETag": ETAG}},
    412: ERROR_RESPONSE,
    428: ERROR_RESPONSE,
}
Status = Annotated[
    Literal[
        "not_started",
        "in_progress",
        "paused",
        "submitted",
        "changes_requested",
        "completed",
        "cancelled",
    ]
    | None,
    Query(),
    WithJsonSchema(
        {
            "type": "string",
            "enum": [
                "not_started",
                "in_progress",
                "paused",
                "submitted",
                "changes_requested",
                "completed",
                "cancelled",
            ],
        }
    ),
]
CaseFilter = Annotated[UUID | None, Query(), WithJsonSchema({"type": "string", "format": "uuid"})]


@router.get(
    "/tasks",
    operation_id="training_tasks_list",
    response_model=TaskPage,
    responses=AUTHENTICATED_ERRORS,
)
def tasks(
    context: Authenticated,
    limit: Limit = 20,
    cursor: Cursor = None,
    status: Status = None,
    case_id: CaseFilter = None,
) -> TaskPage:
    s, actor = context
    rows, cursor = service.list_tasks(s, actor, limit, cursor, status, case_id)
    return TaskPage(
        items=[Task.model_validate(row) for row in rows],
        next_cursor=cursor,
        has_more=cursor is not None,
    )


@router.get(
    "/tasks/{task_id}",
    operation_id="training_tasks_get",
    response_model=Task,
    responses=READ_RESPONSES,
)
def task(task_id: UUID, context: Authenticated, response: Response) -> Task:
    s, actor = context
    row, _ = service.task_access(s, actor, task_id)
    result = Task.model_validate(service.task_payload(s, actor, row))
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.post(
    "/tasks/{task_id}/actions",
    operation_id="training_tasks_action",
    response_model=Task,
    responses=WRITE_RESPONSES,
)
def action(
    task_id: UUID,
    body: TaskAction,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        _, access = service.task_access(s, actor, task_id, True)
        if body.action == "cancel":
            access.require_counselor(actor)
        else:
            access.require_learner(actor)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json", exclude_unset=True),
        version,
        authorize,
        lambda: Task.model_validate(
            service.action(
                s, actor, task_id, body.action, body.reason or "", version, request.state.trace_id
            )
        ),
        etag="version",
    )


@router.put(
    "/tasks/{task_id}/steps/{step_id}",
    operation_id="training_steps_put",
    response_model=Task,
    responses=WRITE_RESPONSES,
)
def progress(
    task_id: UUID,
    step_id: UUID,
    body: ProgressWrite,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> Task:
    s, actor = context
    write_check(request, s, csrf)
    result = Task.model_validate(
        service.update_progress(
            s,
            actor,
            task_id,
            step_id,
            body.status,
            body.attachment_ids,
            version,
            request.state.trace_id,
        )
    )
    response.headers["ETag"] = f'"{result.version}"'
    return result


@router.post(
    "/tasks/{task_id}/events",
    operation_id="training_events",
    response_model=EventReceipt,
    responses=AUTHENTICATED_ERRORS,
)
def events(
    task_id: UUID,
    body: EventBatch,
    context: Authenticated,
    csrf: Csrf,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        _, access = service.task_access(s, actor, task_id, True)
        access.require_learner(actor)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json"),
        None,
        authorize,
        lambda: EventReceipt.model_validate(
            service.record_events(s, actor, task_id, body.model_dump(mode="json")["events"])
        ),
    )


@router.get(
    "/tasks/{task_id}/submissions",
    operation_id="training_submissions_list",
    response_model=SubmissionPage,
    responses=AUTHENTICATED_ERRORS,
)
def submissions(
    task_id: UUID, context: Authenticated, limit: Limit = 20, cursor: Cursor = None
) -> SubmissionPage:
    s, actor = context
    rows, cursor = service.submissions(s, actor, task_id, limit, cursor)
    return SubmissionPage(
        items=[Submission.model_validate(row) for row in rows],
        next_cursor=cursor,
        has_more=cursor is not None,
    )


@router.post(
    "/tasks/{task_id}/submissions",
    operation_id="training_submissions_create",
    response_model=Submission,
    status_code=201,
    responses=CREATED,
)
def submit(
    task_id: UUID,
    body: SubmissionCreate,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        _, access = service.task_access(s, actor, task_id, True)
        access.require_learner(actor)

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json"),
        version,
        authorize,
        lambda: Submission.model_validate(
            service.submit(s, actor, task_id, body.note, version, request.state.trace_id)
        ),
        status=201,
        etag="task_version",
    )


@router.get(
    "/submissions/{submission_id}",
    operation_id="training_submissions_get",
    response_model=Submission,
    responses=READ_RESPONSES,
)
def submission(submission_id: UUID, context: Authenticated, response: Response) -> Submission:
    s, actor = context
    row, task, _ = service.submission_access(s, actor, submission_id)
    result = Submission.model_validate(service.submission_payload(s, row, task))
    response.headers["ETag"] = f'"{result.task_version}"'
    return result


@router.post(
    "/submissions/{submission_id}/feedback",
    operation_id="training_feedback",
    response_model=FeedbackResult,
    status_code=201,
    responses=CREATED,
)
def feedback(
    submission_id: UUID,
    body: FeedbackCreate,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    key: Idempotency,
    request: Request,
) -> JSONResponse:
    s, actor = context

    def authorize() -> None:
        _, _, access = service.submission_access(s, actor, submission_id, True)
        access.require_counselor(actor)

    def apply() -> FeedbackResult:
        support.feedback_annotations(
            s, actor, submission_id, body.annotation_ids, request.state.trace_id
        )
        return FeedbackResult.model_validate(
            service.review(
                s,
                actor,
                submission_id,
                body.model_dump(mode="json"),
                version,
                request.state.trace_id,
                annotations_validated=True,
            )
        )

    return command(
        request,
        s,
        actor,
        csrf,
        key,
        body.model_dump(mode="json"),
        version,
        authorize,
        apply,
        status=201,
        etag="task.version",
    )


@router.get(
    "/cases/{case_id}/records",
    operation_id="training_records",
    response_model=RecordPage,
    responses=AUTHENTICATED_ERRORS,
)
def records(
    case_id: UUID, context: Authenticated, limit: Limit = 20, cursor: Cursor = None
) -> RecordPage:
    s, actor = context
    rows, cursor = service.records(s, actor, case_id, limit, cursor)
    counts = request_counts(s, actor, [UUID(str(row["task_id"])) for row in rows])
    for row in rows:
        row["assistance_requests"] = counts.get(UUID(str(row["task_id"])), 0)
    return RecordPage(
        items=[TrainingRecord.model_validate(row) for row in rows],
        next_cursor=cursor,
        has_more=cursor is not None,
    )
