import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app.core.config import Settings
from app.core.errors import AppError
from app.infrastructure.db import Database

logger = logging.getLogger("job_lens")
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    title: str
    status: int
    code: str
    trace_id: str


def problem_response(
    request: Request, status: int, code: str, title: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid4().hex)
    payload = Problem(
        type=f"urn:job-lens:problem:{code.lower().replace('_', '-')}",
        title=title,
        status=status,
        code=code,
        trace_id=trace_id,
    )
    return JSONResponse(
        payload.model_dump(),
        status_code=status,
        media_type="application/problem+json",
        headers={
            **{
                key: value
                for key, value in (headers or {}).items()
                if key.lower() in {"allow", "retry-after", "www-authenticate"}
            },
            "Cache-Control": "no-store",
            "X-Request-ID": trace_id,
        },
    )


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        db = database or Database.from_settings(config)
        application.state.database = db
        try:
            yield
        finally:
            if database is None:
                db.close()

    api = FastAPI(
        title="Job Lens API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if config.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if config.environment != "production" else None,
    )
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=config.trusted_hosts)

    @api.middleware("http")
    async def observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        candidate = request.headers.get("X-Request-ID", "")
        request.state.trace_id = candidate if _REQUEST_ID.fullmatch(candidate) else uuid4().hex
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Exception messages may contain SQL parameters or private paths.
            logger.error(
                "request_failed type=%s trace_id=%s", type(exc).__name__, request.state.trace_id
            )
            response = problem_response(request, 500, "INTERNAL_ERROR", "服务暂不可用")
        if (
            request.url.path.startswith("/api/")
            and response.status_code >= 400
            and not response.headers.get("content-type", "").startswith("application/problem+json")
        ):
            # Normalize rejections from middleware as well as route exceptions.
            response = problem_response(
                request,
                response.status_code,
                f"HTTP_{response.status_code}",
                "请求无法处理",
                dict(response.headers),
            )
        response.headers["X-Request-ID"] = request.state.trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        logger.info(
            "request method=%s route=%s status=%s duration_ms=%.1f trace_id=%s",
            request.method,
            getattr(route, "path", "unmatched"),
            response.status_code,
            (time.perf_counter() - start) * 1000,
            request.state.trace_id,
        )
        return response

    @api.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem_response(request, exc.status, exc.code, exc.title)

    @api.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(request, 422, "VALIDATION_ERROR", "请求格式不正确")

    @api.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return problem_response(
            request,
            exc.status_code,
            f"HTTP_{exc.status_code}",
            "请求无法处理",
            dict(exc.headers) if exc.headers else None,
        )

    error_response: dict[str, Any] = {
        "description": "Structured failure",
        "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
    }
    errors: dict[int | str, dict[str, Any]] = {"default": error_response}

    @api.get(
        "/api/v1/health/live", operation_id="health_live", response_model=Health, responses=errors
    )
    def live() -> Health:
        return Health(status="ok")

    @api.get(
        "/api/v1/health/ready",
        operation_id="health_ready",
        response_model=Health,
        responses={**errors, 503: error_response},
    )
    def ready(request: Request) -> Health:
        try:
            available = request.app.state.database.ready()
        except Exception:
            available = False
        if not available:
            raise AppError(503, "NOT_READY", "服务尚未就绪")
        return Health(status="ok")

    return api
