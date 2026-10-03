from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.modules.cases import administration
from app.modules.identity import management
from app.modules.identity.queries import is_administrator
from app.web.deps import Authenticated
from app.web.identity import WRITE_RESPONSES, Csrf, Version, write_check
from app.web.schemas import AUTHENTICATED_ERRORS

router = APIRouter()
State = Literal["not_submitted", "pending", "approved", "rejected", "revoked"]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100000)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)


class Administration(Model):
    can_manage_users: bool


class ApplicationWrite(Model):
    statement: Annotated[str, Field(min_length=1, max_length=2000)]


class Certification(Model):
    user_id: UUID
    state: State
    statement: str
    reason: str
    reviewer_id: UUID | None
    reviewed_at: datetime | None
    version: int


class CertificationQueue(Model):
    items: list[Certification]
    total: int


class Reason(Model):
    reason: Annotated[str, Field(min_length=1, max_length=1000)]


class Review(Reason):
    decision: Literal["approved", "rejected", "revoked"]


class AccountStatus(Reason):
    active: bool


class ManagedUser(Model):
    id: UUID
    display_name: str
    active: bool
    roles: list[Literal["learner", "counselor"]]
    version: int


class UserList(Model):
    items: list[ManagedUser]
    total: int


class Assignment(Reason):
    assigned: bool


class ManagedCase(Model):
    id: UUID
    learner_id: UUID
    counselor_ids: list[UUID]
    version: int


class CaseList(Model):
    items: list[ManagedCase]
    total: int


class Event(Model):
    id: UUID
    actor_id: UUID | None
    target_id: UUID
    action: str
    reason: str
    trace_id: str
    created_at: datetime


def etag(response: Response, version: int) -> None:
    response.headers["ETag"] = f'"{version}"'


@router.get(
    "/me/administration",
    operation_id="identity_administration",
    response_model=Administration,
    responses=AUTHENTICATED_ERRORS,
)
def administration_capability(context: Authenticated) -> Administration:
    s, actor = context
    return Administration(can_manage_users=is_administrator(s, actor))


@router.get(
    "/me/counselor-certification",
    operation_id="identity_get_certification",
    response_model=Certification,
    responses=WRITE_RESPONSES,
)
def my_certification(context: Authenticated, response: Response) -> Certification:
    s, actor = context
    result = Certification.model_validate(management.certification(s, actor.user_id))
    etag(response, result.version)
    return result


@router.put(
    "/me/counselor-certification",
    operation_id="identity_submit_certification",
    response_model=Certification,
    responses=WRITE_RESPONSES,
)
def submit_certification(
    body: ApplicationWrite,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> Certification:
    s, actor = context
    write_check(request, s, csrf)
    result = Certification.model_validate(
        management.submit(s, actor, body.statement, version, request.state.trace_id)
    )
    etag(response, result.version)
    return result


@router.get(
    "/admin/users",
    operation_id="identity_admin_users",
    response_model=UserList,
    responses=AUTHENTICATED_ERRORS,
)
def users(context: Authenticated, limit: Limit = 25, offset: Offset = 0) -> UserList:
    s, actor = context
    return UserList.model_validate(management.users(s, actor, limit, offset))


@router.put(
    "/admin/users/{user_id}/status",
    operation_id="identity_admin_status",
    response_model=ManagedUser,
    responses=WRITE_RESPONSES,
)
def account_status(
    user_id: UUID,
    body: AccountStatus,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> ManagedUser:
    s, actor = context
    write_check(request, s, csrf)
    result = ManagedUser.model_validate(
        management.set_status(
            s, actor, user_id, body.active, body.reason, version, request.state.trace_id
        )
    )
    if not body.active:
        administration.revoke_counselor_grants(s, actor, user_id, request.state.trace_id)
    etag(response, result.version)
    return result


@router.get(
    "/admin/counselor-certifications",
    operation_id="identity_admin_certifications",
    response_model=CertificationQueue,
    responses=AUTHENTICATED_ERRORS,
)
def certification_queue(
    context: Authenticated, limit: Limit = 25, offset: Offset = 0, state: State | None = None
) -> CertificationQueue:
    s, actor = context
    return CertificationQueue.model_validate(management.queue(s, actor, limit, offset, state))


@router.put(
    "/admin/counselor-certifications/{user_id}",
    operation_id="identity_admin_review",
    response_model=Certification,
    responses=WRITE_RESPONSES,
)
def review_certification(
    user_id: UUID,
    body: Review,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> Certification:
    s, actor = context
    write_check(request, s, csrf)
    result = Certification.model_validate(
        management.review(
            s, actor, user_id, body.decision, body.reason, version, request.state.trace_id
        )
    )
    if body.decision == "revoked":
        administration.revoke_counselor_grants(s, actor, user_id, request.state.trace_id)
    etag(response, result.version)
    return result


@router.get(
    "/admin/cases",
    operation_id="cases_admin_list",
    response_model=CaseList,
    responses=AUTHENTICATED_ERRORS,
)
def cases(context: Authenticated, limit: Limit = 25, offset: Offset = 0) -> CaseList:
    s, actor = context
    return CaseList.model_validate(administration.list_cases(s, actor, limit, offset))


@router.put(
    "/admin/cases/{case_id}/counselors/{counselor_id}",
    operation_id="cases_admin_assign",
    response_model=ManagedCase,
    responses=WRITE_RESPONSES,
)
def assign(
    case_id: UUID,
    counselor_id: UUID,
    body: Assignment,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> ManagedCase:
    s, actor = context
    write_check(request, s, csrf)
    result = ManagedCase.model_validate(
        administration.assign(
            s, actor, case_id, counselor_id, body.assigned, version, request.state.trace_id
        )
    )
    management.audit(
        s,
        actor,
        counselor_id,
        "identity.case_assigned" if body.assigned else "identity.case_unassigned",
        body.reason,
        request.state.trace_id,
    )
    s.flush()
    etag(response, result.version)
    return result


@router.get(
    "/admin/audit",
    operation_id="identity_admin_audit",
    response_model=list[Event],
    responses=AUTHENTICATED_ERRORS,
)
def audit(context: Authenticated, limit: Limit = 25, offset: Offset = 0) -> list[Event]:
    s, actor = context
    return [Event.model_validate(event) for event in management.events(s, actor, limit, offset)]
