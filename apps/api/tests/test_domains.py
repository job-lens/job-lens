from uuid import uuid4

import pytest
from app.core.errors import AppError
from app.core.types import Actor
from app.modules.cases.public import CaseAccess
from app.modules.identity.public import MediaPreferences
from app.modules.sop.public import PublishedSop
from app.modules.sop.rules import validate_publication
from app.modules.support.public import Marker
from app.modules.support.rules import transition_assistance
from app.modules.training.public import TRANSITIONS, TaskStatus
from app.modules.training.rules import transition, validate_feedback


@pytest.fixture
def actors():
    learner = Actor(uuid4(), frozenset({"learner"}))
    counselor = Actor(uuid4(), frozenset({"counselor"}))
    return learner, counselor, CaseAccess(uuid4(), learner.user_id, frozenset({counselor.user_id}))


@pytest.mark.parametrize("status", list(TaskStatus))
@pytest.mark.parametrize(
    "action",
    ["start", "pause", "resume", "submit", "pass", "request_changes", "cancel", "invented"],
)
def test_transition_matrix(actors, status, action):
    learner, counselor, access = actors
    actor = counselor if action in {"pass", "request_changes", "cancel"} else learner
    if (status, action) in TRANSITIONS:
        assert (
            transition(actor, access, status, action, "测试原因") == TRANSITIONS[(status, action)]
        )
    else:
        with pytest.raises(AppError):
            transition(actor, access, status, action, "测试原因")


def test_cross_case_and_role_authorization(actors):
    learner, counselor, access = actors
    with pytest.raises(AppError) as exc:
        access.require_read(Actor(uuid4(), frozenset({"counselor"})))
    assert exc.value.status == 404
    with pytest.raises(AppError) as exc:
        transition(learner, access, TaskStatus.SUBMITTED, "pass")
    assert exc.value.status == 403
    with pytest.raises(AppError):
        access.require_read(Actor(learner.user_id, frozenset({"counselor"})))
    with pytest.raises(AppError):
        transition(counselor, access, TaskStatus.IN_PROGRESS, "cancel")


def test_feedback_invariants():
    step = uuid4()
    validate_feedback("passed", "完成", (), frozenset({step}))
    validate_feedback("changes_requested", "修改日期", (step,), frozenset({step}))
    for outcome, message, redo in [
        ("passed", "完成", (step,)),
        ("changes_requested", "修改", ()),
        ("passed", " ", ()),
        ("changes_requested", "修改", (uuid4(),)),
    ]:
        with pytest.raises(AppError):
            validate_feedback(outcome, message, redo, frozenset({step}))


def test_sop_publication_rules(actors):
    _, counselor, access = actors
    content = PublishedSop(uuid4(), access.case_id, (uuid4(),))
    values = dict(
        state="draft",
        match_confirmed=True,
        goal="检查标题",
        instructions=("对照样例",),
        materials_ready=True,
        has_active_task=False,
    )
    validate_publication(counselor, access, content, **values)
    for patch in [
        dict(state="published"),
        dict(goal=" "),
        dict(materials_ready=False),
        dict(has_active_task=True),
        dict(match_confirmed=False),
        dict(instructions=()),
    ]:
        with pytest.raises(AppError):
            validate_publication(counselor, access, content, **(values | patch))


@pytest.mark.parametrize(
    "marker",
    [
        Marker(-0.1, 0, "位置"),
        Marker(0, 0, " "),
        Marker(0, 0, "位置", 0.2, None),
        Marker(0.9, 0, "位置", 0.2, 0.1),
        Marker(float("nan"), 0, "位置"),
        Marker(0, 0, "位置", 0, 0.1),
    ],
)
def test_marker_invalid_geometry(marker):
    with pytest.raises(ValueError):
        marker.validate()


def test_marker_and_quiet_mode():
    Marker(0, 0, "标题").validate()
    Marker(0.1, 0.1, "标题", 0.9, 0.9).validate()
    p = MediaPreferences(True, True, True, 1)
    assert not p.can_speak and not p.can_vibrate


def test_assistance_state_machine(actors):
    learner, counselor, access = actors
    assert transition_assistance(counselor, access, "queued", "accept") == "accepted"
    assert transition_assistance(counselor, access, "accepted", "resolve") == "resolved"
    assert transition_assistance(learner, access, "queued", "cancel") == "cancelled"
    with pytest.raises(AppError):
        transition_assistance(learner, access, "resolved", "cancel")
