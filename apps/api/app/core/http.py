import re

from app.core.errors import AppError

_VERSION = re.compile(r'"([1-9][0-9]{0,9})"')
_KEY = re.compile(r"[!-~]{16,128}")


def require_version(value: str | None, current: int) -> None:
    if value is None:
        raise AppError(428, "PRECONDITION_REQUIRED", "请读取最新版本后重试")
    match = _VERSION.fullmatch(value)
    if not match or int(match[1]) > 2147483647:
        raise AppError(400, "INVALID_ETAG", "版本格式无效")
    if int(match[1]) != current:
        raise AppError(412, "VERSION_CONFLICT", "内容已更新，请刷新后重试")


def require_idempotency_key(value: str | None) -> str:
    if value is None or not _KEY.fullmatch(value):
        raise AppError(400, "INVALID_IDEMPOTENCY_KEY", "请求标识无效")
    return value
