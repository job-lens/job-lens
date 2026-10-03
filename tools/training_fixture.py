"""Synthetic local acceptance data; never creates accounts in ordinary databases."""

import os
from typing import cast
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.security import hash_password
from app.core.types import Actor, JsonObject
from app.infrastructure.db import Database
from app.modules.cases.models import Case, CaseGrant, SupportMatch
from app.modules.identity.models import Preferences, Profile, User, UserRole
from app.modules.sop import service as sop
from app.modules.training import service as training
from sqlalchemy import select
from sqlalchemy.engine import make_url


def main() -> None:
    settings = Settings()
    name = make_url(settings.database_url.get_secret_value()).database or ""
    if settings.environment != "test" or not name.endswith("_test"):
        raise SystemExit("Training fixtures require environment=test and a *_test database")
    password = os.environ["JOB_LENS_FIXTURE_PASSWORD"]
    if len(password) < 12:
        raise SystemExit("Fixture password must contain at least 12 characters")
    database = Database.from_settings(settings)
    try:
        with database.transaction() as s:
            users = {}
            for role, display in [("learner", "体验学员"), ("counselor", "体验辅导员")]:
                login = "mock_" + role
                if s.scalar(select(User.id).where(User.login_name == login)):
                    raise SystemExit("Fixture exists; refusing to overwrite any account")
                user = User(login_name=login, password_hash=hash_password(password))
                s.add(user)
                s.flush()
                s.add_all(
                    [
                        UserRole(user_id=user.id, role=role),
                        Profile(
                            user_id=user.id,
                            display_name=display,
                            sensory_preferences=["安静环境", "文字指引"],
                            communication_preference="请先用文字说明，一次讲清楚一步。",
                            work_notes="此账号及个案均为本地合成验收数据。",
                        ),
                        Preferences(user_id=user.id),
                    ]
                )
                users[role] = user.id
            s.flush()
            learner = Actor(users["learner"], frozenset({"learner"}))
            counselor = Actor(users["counselor"], frozenset({"counselor"}))
            for index, title in enumerate(["文件整理", "物品核对", "整理工作台"]):
                case = Case(learner_id=learner.user_id, lifecycle="active", version=2)
                s.add(case)
                s.flush()
                s.add_all(
                    [
                        CaseGrant(case_id=case.id, counselor_id=counselor.user_id),
                        SupportMatch(
                            case_id=case.id,
                            direction=title,
                            focus="按文字提示分步完成",
                            basis="本地合成体验个案",
                            state="confirmed",
                            version=3,
                        ),
                    ]
                )
                s.flush()
                plan = sop.create_plan(s, counselor, case.id, title, "local-fixture")
                revision_id = cast(UUID, plan["draft_revision_id"])
                instructions = [
                    "先核对清单上的名称。",
                    "按顺序放到对应的位置。",
                    "再检查一次，确认没有遗漏。",
                ]
                body: JsonObject = dict(
                    goal="按清楚的步骤完成" + title,
                    steps=[
                        dict(
                            id=str(uuid4()),
                            position=position,
                            instruction=text,
                            media_ids=[],
                            estimated_seconds=120,
                            evidence_required=False,
                        )
                        for position, text in enumerate(instructions, 1)
                    ],
                    reminder=dict(speech_enabled=False, vibration_enabled=False, prompt_level=2),
                )
                sop.save_revision(s, counselor, revision_id, body, '"1"', "local-fixture")
                sop.publish(s, counselor, revision_id, '"2"', "local-fixture")
                task = training.create_for_publication(
                    s, counselor, revision_id, None, "local-fixture"
                )
                if index:
                    training.action(s, learner, task.id, "start", "", '"1"', "local-fixture")
                    for step in cast(list[JsonObject], body["steps"]):
                        training.update_progress(
                            s,
                            learner,
                            task.id,
                            UUID(str(step["id"])),
                            "completed",
                            [],
                            f'"{task.version}"',
                            "local-fixture",
                        )
                    submission = training.submit(
                        s, learner, task.id, "已按步骤检查。", f'"{task.version}"', "local-fixture"
                    )
                    if index == 2:
                        training.review(
                            s,
                            counselor,
                            UUID(str(submission["id"])),
                            dict(
                                outcome="changes_requested",
                                message="前两步已经完成。第三步请再核对一次，有需要时可以联系我。",
                                tags=["other"],
                                redo_step_ids=[str(cast(list[JsonObject], body["steps"])[2]["id"])],
                                annotation_ids=[],
                            ),
                            f'"{task.version}"',
                            "local-fixture",
                        )
        print("PASS: synthetic mock_learner / mock_counselor and 3 training scenarios")
    finally:
        database.close()


if __name__ == "__main__":
    main()
