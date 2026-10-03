from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from app.core.errors import AppError
from app.infrastructure.db import utcnow
from app.modules.identity import service
from app.modules.identity.queries import load_user
from app.web.deps import Authenticated, Transaction
from app.web.problem import problem_response
from app.web.schemas import (
    AUTHENTICATED_ERRORS,
    ERROR_RESPONSE,
    ERRORS,
    Capabilities,
    CsrfToken,
    LoginRequest,
    LoginResult,
    Preferences,
    PreferencesWrite,
    Profile,
    ProfileWrite,
    User,
)

router = APIRouter()
Csrf = Annotated[str, Header(alias="X-CSRF-Token", min_length=16, max_length=256)]
Version = Annotated[str, Header(alias="If-Match", json_schema_extra={"pattern": '^"[1-9][0-9]*"$'})]
ETAG = {
    "description": "Quoted resource version.",
    "schema": {"type": "string", "pattern": '^"[1-9][0-9]*"$'},
}
PERSONAL_RESPONSES = {**AUTHENTICATED_ERRORS, 200: {"headers": {"ETag": ETAG}}}
WRITE_RESPONSES = {**PERSONAL_RESPONSES, 412: ERROR_RESPONSE, 428: ERROR_RESPONSE}
COOKIE = "__Host-jl_session"


def set_session(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE, token, max_age=43200, secure=True, httponly=True, samesite="lax", path="/"
    )


def write_check(request: Request, session: Transaction, csrf: str) -> None:
    service.check_write(
        session,
        request.cookies.get(COOKIE),
        request.headers.get("origin"),
        request.app.state.settings.public_origin,
        csrf,
        utcnow(),
    )


@router.get("/auth/csrf", operation_id="auth_csrf", response_model=CsrfToken, responses=ERRORS)
def auth_csrf(request: Request, response: Response, session: Transaction) -> CsrfToken:
    origin = request.headers.get("origin")
    if origin and origin != request.app.state.settings.public_origin:
        raise AppError(403, "CSRF_REJECTED", "请求校验失败")
    service.take_budget(
        session,
        "csrf-client:" + (request.client.host if request.client else "unknown"),
        120,
        timedelta(minutes=1),
        utcnow(),
    )
    grant = service.csrf_grant(session, request.cookies.get(COOKIE), utcnow())
    if grant.token:
        set_session(response, grant.token)
    return CsrfToken(csrf_token=grant.csrf_token)


@router.post(
    "/auth/login",
    operation_id="auth_login",
    response_model=LoginResult,
    responses=AUTHENTICATED_ERRORS,
)
def auth_login(
    body: LoginRequest, csrf: Csrf, request: Request, response: Response, session: Transaction
) -> LoginResult | JSONResponse:
    try:
        grant = service.login(
            session,
            request.cookies.get(COOKIE),
            request.headers.get("origin"),
            request.app.state.settings.public_origin,
            csrf,
            body.login_name,
            body.password,
            utcnow(),
            request.state.trace_id,
            request.client.host if request.client else "unknown",
        )
    except AppError as exc:
        # Returning the Problem allows failed-attempt budgets to commit.
        return problem_response(request, exc.status, exc.code, exc.title)
    assert grant.token is not None and grant.user is not None
    set_session(response, grant.token)
    return LoginResult(
        user=User(
            id=grant.user.id, display_name=grant.user.display_name, roles=list(grant.user.roles)
        ),
        csrf_token=grant.csrf_token,
    )


@router.post(
    "/auth/logout", operation_id="auth_logout", status_code=204, responses=AUTHENTICATED_ERRORS
)
def auth_logout(context: Authenticated, csrf: Csrf, request: Request) -> Response:
    session, actor = context
    service.logout(
        session,
        actor,
        request.cookies.get(COOKIE),
        request.headers.get("origin"),
        request.app.state.settings.public_origin,
        csrf,
        utcnow(),
        request.state.trace_id,
    )
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response


@router.get("/me", operation_id="identity_me", response_model=User, responses=AUTHENTICATED_ERRORS)
def identity_me(context: Authenticated) -> User:
    session, actor = context
    view = load_user(session, actor)
    return User(id=view.id, display_name=view.display_name, roles=list(view.roles))


@router.get(
    "/me/preferences",
    operation_id="identity_get_preferences",
    response_model=Preferences,
    responses=PERSONAL_RESPONSES,
)
def get_preferences(context: Authenticated, response: Response) -> Preferences:
    session, actor = context
    view = Preferences.model_validate(service.get_preferences(session, actor))
    response.headers["ETag"] = f'"{view.version}"'
    return view


@router.put(
    "/me/preferences",
    operation_id="identity_put_preferences",
    response_model=Preferences,
    responses=WRITE_RESPONSES,
)
def put_preferences(
    body: PreferencesWrite,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> Preferences:
    session, actor = context
    write_check(request, session, csrf)
    view = Preferences.model_validate(
        service.save_personal(
            session, actor, "preferences", body.model_dump(), version, request.state.trace_id
        )
    )
    response.headers["ETag"] = f'"{view.version}"'
    return view


@router.get(
    "/me/profile",
    operation_id="identity_get_profile",
    response_model=Profile,
    responses=PERSONAL_RESPONSES,
)
def get_profile(context: Authenticated, response: Response) -> Profile:
    session, actor = context
    view = Profile.model_validate(service.get_profile(session, actor))
    response.headers["ETag"] = f'"{view.version}"'
    return view


@router.put(
    "/me/profile",
    operation_id="identity_put_profile",
    response_model=Profile,
    responses=WRITE_RESPONSES,
)
def put_profile(
    body: ProfileWrite,
    context: Authenticated,
    csrf: Csrf,
    version: Version,
    request: Request,
    response: Response,
) -> Profile:
    session, actor = context
    write_check(request, session, csrf)
    view = Profile.model_validate(
        service.save_personal(
            session, actor, "profile", body.model_dump(), version, request.state.trace_id
        )
    )
    response.headers["ETag"] = f'"{view.version}"'
    return view


@router.get(
    "/capabilities",
    operation_id="identity_capabilities",
    response_model=Capabilities,
    responses=AUTHENTICATED_ERRORS,
)
def capabilities(context: Authenticated) -> Capabilities:
    return Capabilities(
        screenshot_annotation=False,
        realtime_calls=False,
        sop_conversion=False,
        realtime_ar=False,
        precise_location=False,
    )
