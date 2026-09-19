from uuid import UUID

from app.core.errors import AppError, conflict
from app.core.types import Actor
from app.modules.cases.public import CaseAccess
from app.modules.training.public import TRANSITIONS, TaskStatus


def transition(
    actor: Actor, access: CaseAccess, status: TaskStatus, action: str, reason: str = ""
) -> TaskStatus:
    if action in {"pass", "request_changes", "cancel"}:
        access.require_counselor(actor)
    else:
        access.require_learner(actor)
    if action == "cancel" and not reason.strip():
        raise AppError(422, "REASON_REQUIRED", "请填写取消原因")
    target = TRANSITIONS.get((status, action))
    if target is None:
        raise conflict()
    return target


def validate_feedback(
    outcome: str, message: str, redo_ids: tuple[UUID, ...], step_ids: frozenset[UUID]
) -> None:
    if outcome not in {"passed", "changes_requested"} or not message.strip() or len(message) > 500:
        raise AppError(422, "INVALID_FEEDBACK", "请填写有效反馈")
    if len(set(redo_ids)) != len(redo_ids) or not set(redo_ids) <= step_ids:
        raise AppError(422, "INVALID_REDO_STEPS", "返工步骤无效")
    if (outcome == "changes_requested") != bool(redo_ids):
        raise AppError(422, "INVALID_REDO_STEPS", "返工结论与步骤不一致")
