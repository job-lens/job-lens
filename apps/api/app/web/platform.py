import logging

from fastapi import APIRouter, Request

from app.core.errors import AppError
from app.infrastructure.db import Database
from app.web.schemas import ERROR_RESPONSE, ERRORS, Health

router = APIRouter(prefix="/health")
logger = logging.getLogger("job_lens.health")


@router.get("/live", operation_id="health_live", response_model=Health, responses=ERRORS)
def health_live() -> Health:
    return Health(status="ok")


@router.get(
    "/ready",
    operation_id="health_ready",
    response_model=Health,
    responses={**ERRORS, 503: ERROR_RESPONSE},
)
def health_ready(request: Request) -> Health:
    database: Database = request.app.state.database
    try:
        available = database.ready()
    except Exception as exc:
        # Database exception messages may include private connection details.
        logger.warning("database_readiness_failed type=%s", type(exc).__name__)
        available = False
    if not available:
        raise AppError(503, "NOT_READY", "服务尚未就绪")
    return Health(status="ok")
