from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from app.web.schemas import Problem

# Only headers that carry protocol meaning survive; the rest may leak internals.
_FORWARDED = {"allow", "retry-after", "www-authenticate"}


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
            **{k: v for k, v in (headers or {}).items() if k.lower() in _FORWARDED},
            "Cache-Control": "no-store",
            "X-Request-ID": trace_id,
        },
    )
