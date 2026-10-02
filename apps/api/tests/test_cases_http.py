from uuid import uuid4

import pytest
import test_postgres as postgres_fixtures
from app.core.config import Settings
from app.core.security import hash_password
from app.infrastructure.db import utcnow
from app.main import create_app
from app.modules.cases.models import Case, CaseGrant, SupportMatch
from app.modules.identity.models import Preferences, Profile, User, UserRole
from fastapi.testclient import TestClient

pytestmark = pytest.mark.postgres
database = postgres_fixtures.database
db = postgres_fixtures.db


@pytest.fixture
def scenario(db):
    with db.transaction() as s:
        users = {}
        for name, role in [
            ("learner", "learner"),
            ("counselor", "counselor"),
            ("outsider", "counselor"),
        ]:
            user = User(login_name=name, password_hash=hash_password("training-password"))
            s.add(user)
            s.flush()
            s.add_all(
                [
                    UserRole(user_id=user.id, role=role),
                    Profile(user_id=user.id, display_name=name),
                    Preferences(user_id=user.id),
                ]
            )
            users[name] = user.id
        case = Case(learner_id=users["learner"])
        s.add(case)
        s.flush()
        s.add_all(
            [
                CaseGrant(case_id=case.id, counselor_id=users["counselor"]),
                SupportMatch(case_id=case.id),
            ]
        )
        return {"case": str(case.id), **users}


@pytest.fixture
def client(db, scenario):
    config = Settings(
        database_url=str(db.engine.url),
        public_origin="https://testserver",
        trusted_hosts=["testserver"],
        environment="test",
        _env_file=None,
    )
    with TestClient(create_app(config, db), base_url="https://testserver") as client:
        yield client


def login(client, name="counselor"):
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    r = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://testserver", "X-CSRF-Token": token},
        json={"login_name": name, "password": "training-password"},
    )
    assert r.status_code == 200
    return {"Origin": "https://testserver", "X-CSRF-Token": r.json()["csrf_token"]}


def test_scoped_cases_profile_dashboard_and_wrong_role(client, scenario):
    assert client.get("/api/v1/cases").status_code == 401
    login(client)
    result = client.get("/api/v1/cases")
    assert result.status_code == 200 and len(result.json()["items"]) == 1
    case = result.json()["items"][0]
    assert case["display_status"] == "pending_match"
    assert client.get("/api/v1/cases/" + scenario["case"]).headers["etag"] == '"1"'
    profile = client.get("/api/v1/cases/" + scenario["case"] + "/profile")
    assert profile.status_code == 200 and profile.json()["display_name"] == "learner"
    assert profile.json()["preferences"]["quiet_mode"] is True
    assert client.get("/api/v1/dashboard?view=counselor").status_code == 200
    login(client, "learner")
    assert client.get("/api/v1/dashboard?view=counselor").status_code == 403
    assert client.get("/api/v1/cases").json()["items"][0]["id"] == scenario["case"]
    login(client, "outsider")
    assert client.get("/api/v1/cases").json()["items"] == []
    for suffix in ["", "/profile", "/match", "/materials"]:
        assert client.get("/api/v1/cases/" + scenario["case"] + suffix).status_code == 404


def test_match_saves_and_confirms_once_with_etag_and_complete_content(client, scenario):
    headers = login(client)
    path = "/api/v1/cases/" + scenario["case"] + "/match"
    assert client.get(path).headers["etag"] == '"1"'
    confirm = {**headers, "If-Match": '"1"', "Idempotency-Key": str(uuid4())}
    assert client.post(path + "/confirm", headers=confirm).status_code == 409
    body = {
        "direction": "文件整理",
        "focus": "核对文件名",
        "basis": "使用文字指引",
        "cycle_weeks": 4,
    }
    assert client.put(path, headers=headers, json=body).status_code == 428
    save = client.put(path, headers={**headers, "If-Match": '"1"'}, json=body)
    assert save.status_code == 200 and save.json()["version"] == 2
    assert client.put(path, headers={**headers, "If-Match": '"1"'}, json=body).status_code == 412
    confirm = {**headers, "If-Match": '"2"', "Idempotency-Key": str(uuid4())}
    done = client.post(path + "/confirm", headers=confirm)
    assert done.status_code == 200 and done.json()["state"] == "confirmed"
    assert client.post(path + "/confirm", headers=confirm).json() == done.json()
    assert client.put(path, headers={**headers, "If-Match": '"3"'}, json=body).status_code == 409
    assert client.get("/api/v1/cases/" + scenario["case"]).json()["display_status"] == "sop_pending"


def test_learner_cannot_edit_match_and_revoked_grant_cannot_replay(db, client, scenario):
    headers = login(client, "learner")
    path = "/api/v1/cases/" + scenario["case"] + "/match"
    body = {"direction": "任务", "focus": "步骤", "basis": "沟通", "cycle_weeks": 4}
    assert client.put(path, headers={**headers, "If-Match": '"1"'}, json=body).status_code == 403
    headers = login(client)
    client.put(path, headers={**headers, "If-Match": '"1"'}, json=body)
    command = {**headers, "If-Match": '"2"', "Idempotency-Key": str(uuid4())}
    assert client.post(path + "/confirm", headers=command).status_code == 200
    with db.transaction() as s:
        grant = s.get(CaseGrant, (scenario["case"], scenario["counselor"]))
        grant.revoked_at = utcnow()
    assert client.post(path + "/confirm", headers=command).status_code == 404


def test_case_pagination_is_stable_and_bound_to_scope(db, client, scenario):
    with db.transaction() as s:
        for _ in range(3):
            case = Case(learner_id=scenario["learner"])
            s.add(case)
            s.flush()
            s.add(CaseGrant(case_id=case.id, counselor_id=scenario["counselor"]))
    login(client)
    first = client.get("/api/v1/cases?limit=2").json()
    assert len(first["items"]) == 2 and first["has_more"]
    second = client.get("/api/v1/cases", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 2 and not second["has_more"]
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    assert client.get("/api/v1/cases?cursor=broken").status_code == 400
    login(client, "learner")
    assert client.get("/api/v1/cases", params={"cursor": first["next_cursor"]}).status_code == 400
