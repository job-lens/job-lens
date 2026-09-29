from app.core.errors import AppError, conflict
from app.core.types import Actor
from app.modules.cases.public import CaseAccess
from app.modules.sop.public import PublishedSop


def validate_publication(
    actor: Actor,
    access: CaseAccess,
    content: PublishedSop,
    *,
    state: str,
    match_confirmed: bool,
    goal: str,
    instructions: tuple[str, ...],
    materials_ready: bool,
    has_active_task: bool,
) -> None:
    access.require_counselor(actor)
    if content.case_id != access.case_id:
        raise AppError(422, "CONTEXT_MISMATCH", "内容所属个案不一致")
    if state != "draft" or not match_confirmed:
        raise conflict()
    if has_active_task:
        raise conflict("ACTIVE_TASK_EXISTS")
    steps = content.step_ids
    if not goal.strip() or not 1 <= len(steps) <= 100 or len(set(steps)) != len(steps):
        raise AppError(422, "INVALID_SOP", "请完善训练目标与步骤")
    if len(instructions) != len(steps) or any(not item.strip() for item in instructions):
        raise AppError(422, "INVALID_SOP", "步骤说明不能为空")
    if not materials_ready:
        raise conflict("FILE_NOT_READY")
