from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.infrastructure.idempotency import CommandResult, Scope, execute_once, fingerprint
from app.infrastructure.notifications import mark_read, read_notifications, require_notification
from app.web.business_schemas import Notification, NotificationPage
from app.web.commands import Idempotency, Limit
from app.web.deps import Authenticated
from app.web.identity import Csrf, write_check
from app.web.schemas import AUTHENTICATED_ERRORS, ERROR_RESPONSE

router = APIRouter()
After = Annotated[str, Query(max_length=20, pattern=r"^(0|[1-9][0-9]*)$")]


@router.get(
    "/notifications",
    operation_id="notifications_list",
    response_model=NotificationPage,
    responses={**AUTHENTICATED_ERRORS, 410: ERROR_RESPONSE},
)
def notifications(
    context: Authenticated, after_seq: After = "0", limit: Limit = 20
) -> NotificationPage:
    s, actor = context
    page = read_notifications(s, actor.user_id, int(after_seq), limit)
    return NotificationPage(
        items=[
            Notification(
                id=row.id,
                seq=str(row.seq),
                type=row.kind,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                created_at=row.created_at,
                read_at=row.read_at,
            )
            for row in page.items
        ],
        next_seq=page.next_seq,
        has_more=page.has_more,
    )


@router.post(
    "/notifications/{notification_id}/read",
    operation_id="notifications_read",
    status_code=204,
    responses=AUTHENTICATED_ERRORS,
)
def read(
    notification_id: UUID, context: Authenticated, csrf: Csrf, key: Idempotency, request: Request
) -> Response:
    s, actor = context
    write_check(request, s, csrf)

    def authorize() -> None:
        require_notification(s, actor.user_id, notification_id)

    def apply() -> CommandResult:
        mark_read(s, actor.user_id, notification_id)
        return CommandResult(204, None, {})

    result = execute_once(
        s,
        Scope(actor.user_id, request.method, request.url.path, key),
        fingerprint({}),
        authorize,
        apply,
    )
    return Response(status_code=result.status)
