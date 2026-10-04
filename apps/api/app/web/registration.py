from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.core.errors import AppError
from app.infrastructure.db import utcnow
from app.modules.identity import registration, service
from app.web.deps import Transaction
from app.web.identity import COOKIE, Csrf, set_session
from app.web.problem import problem_response
from app.web.schemas import (
    ERRORS,
    EmailAccepted,
    EmailRequest,
    LoginResult,
    PasswordResetRequest,
    RegistrationRequest,
    User,
)

router = APIRouter()


def check(request: Request, session: Transaction, csrf: str) -> None:
    service.check_write(
        session,
        request.cookies.get(COOKIE),
        request.headers.get("origin"),
        request.app.state.settings.public_origin,
        csrf,
        utcnow(),
    )


def send_request(
    body: EmailRequest,
    csrf: str,
    request: Request,
    session: Transaction,
    purpose: Literal["registration", "reset"],
) -> EmailAccepted | JSONResponse:
    try:
        check(request, session, csrf)
        registration.request_email(
            session,
            request.app.state.settings,
            body.email,
            purpose,
            request.client.host if request.client else "unknown",
            utcnow(),
            request.state.trace_id,
        )
    except AppError as exc:
        return problem_response(request, exc.status, exc.code, exc.title)
    return EmailAccepted(message="请求已受理，请查看邮箱。")


@router.post(
    "/auth/registration-code",
    operation_id="auth_registration_code",
    response_model=EmailAccepted,
    status_code=202,
    responses=ERRORS,
)
def registration_code(
    body: EmailRequest, csrf: Csrf, request: Request, session: Transaction
) -> EmailAccepted | JSONResponse:
    return send_request(body, csrf, request, session, "registration")


@router.post(
    "/auth/password-reset-requests",
    operation_id="auth_password_reset_request",
    response_model=EmailAccepted,
    status_code=202,
    responses=ERRORS,
)
def reset_request(
    body: EmailRequest, csrf: Csrf, request: Request, session: Transaction
) -> EmailAccepted | JSONResponse:
    return send_request(body, csrf, request, session, "reset")


@router.post(
    "/auth/register",
    operation_id="auth_register",
    response_model=LoginResult,
    status_code=201,
    responses=ERRORS,
)
def register(
    body: RegistrationRequest,
    csrf: Csrf,
    request: Request,
    response: Response,
    session: Transaction,
) -> LoginResult | JSONResponse:
    try:
        now = utcnow()
        old = service.check_write(
            session,
            request.cookies.get(COOKIE),
            request.headers.get("origin"),
            request.app.state.settings.public_origin,
            csrf,
            now,
        )
        service.take_budget(
            session,
            "register-client:" + (request.client.host if request.client else "unknown"),
            30,
            timedelta(minutes=15),
            now,
        )
        grant = registration.register(
            session,
            body.email,
            body.code,
            body.password,
            body.display_name,
            now,
            request.state.trace_id,
        )
        old.revoked_at = now
    except AppError as exc:
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
    "/auth/password-resets", operation_id="auth_password_reset", status_code=204, responses=ERRORS
)
def reset(
    body: PasswordResetRequest, csrf: Csrf, request: Request, session: Transaction
) -> Response:
    try:
        now = utcnow()
        check(request, session, csrf)
        service.take_budget(
            session,
            "reset-submit-client:" + (request.client.host if request.client else "unknown"),
            30,
            timedelta(minutes=15),
            now,
        )
        registration.reset_password(session, body.token, body.password, now, request.state.trace_id)
    except AppError as exc:
        return problem_response(request, exc.status, exc.code, exc.title)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response
