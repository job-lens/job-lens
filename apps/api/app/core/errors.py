class AppError(Exception):
    def __init__(self, status: int, code: str, title: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.title = title


def forbidden() -> AppError:
    return AppError(403, "FORBIDDEN", "无权执行此操作")


def not_found() -> AppError:
    return AppError(404, "NOT_FOUND", "内容不存在或不可访问")


def conflict(code: str = "STATE_CONFLICT") -> AppError:
    return AppError(409, code, "状态已变更，请刷新后重试")


def unauthenticated() -> AppError:
    return AppError(401, "UNAUTHENTICATED", "请先登录")
