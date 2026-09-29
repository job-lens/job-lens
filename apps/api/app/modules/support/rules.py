from typing import Literal

from app.core.errors import conflict
from app.core.types import Actor
from app.modules.cases.public import CaseAccess

type AssistanceState = Literal["queued", "accepted", "resolved", "cancelled"]


def transition_assistance(
    actor: Actor, access: CaseAccess, state: AssistanceState, action: str
) -> AssistanceState:
    if action == "cancel":
        access.require_learner(actor)
        if state in {"queued", "accepted"}:
            return "cancelled"
    else:
        access.require_counselor(actor)
        if action == "accept" and state == "queued":
            return "accepted"
        if action == "resolve" and state == "accepted":
            return "resolved"
    raise conflict()
