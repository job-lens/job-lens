from uuid import uuid4

import pytest
import test_cases_http as fixtures
from test_cases_http import login

database = fixtures.database
db = fixtures.db
client = fixtures.client
scenario = fixtures.scenario

pytestmark = pytest.mark.postgres


def setup_plan(client, scenario):
    headers = login(client)
    match = "/api/v1/cases/" + scenario["case"] + "/match"
    r = client.put(
        match,
        headers={**headers, "If-Match": '"1"'},
        json={"direction": "文件整理", "focus": "检查名称", "basis": "文字引导", "cycle_weeks": 4},
    )
    assert r.status_code == 200
    assert (
        client.post(
            match + "/confirm",
            headers={**headers, "If-Match": '"2"', "Idempotency-Key": str(uuid4())},
        ).status_code
        == 200
    )
    r = client.post(
        "/api/v1/cases/" + scenario["case"] + "/sop-plans",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"title": "整理文件"},
    )
    assert r.status_code == 201, r.text
    plan = r.json()
    return headers, plan, "/api/v1/sop-revisions/" + plan["draft_revision_id"]


def content():
    return {
        "goal": "独立整理两份文件",
        "steps": [
            {
                "id": str(uuid4()),
                "position": 1,
                "instruction": "核对文件名称",
                "media_ids": [],
                "estimated_seconds": 60,
                "evidence_required": False,
            }
        ],
        "reminder": {"speech_enabled": False, "vibration_enabled": False, "prompt_level": 1},
    }


def test_save_publish_freezes_and_creates_unique_task(client, scenario):
    headers, plan, path = setup_plan(client, scenario)
    body = content()
    assert client.put(path, headers=headers, json=body).status_code == 428
    r = client.put(path, headers={**headers, "If-Match": '"1"'}, json=body)
    assert r.status_code == 200 and r.json()["version"] == 2
    assert client.put(path, headers={**headers, "If-Match": '"1"'}, json=body).status_code == 412
    command = {**headers, "If-Match": '"2"', "Idempotency-Key": str(uuid4())}
    result = client.post(path + "/publish", headers=command, json={"due_on": None})
    assert result.status_code == 200, result.text
    assert (
        client.post(path + "/publish", headers=command, json={"due_on": None}).json()
        == result.json()
    )
    published = client.get(path).json()
    assert published["state"] == "published" and published["steps"] == body["steps"]
    assert client.put(path, headers={**headers, "If-Match": '"3"'}, json=body).status_code == 409
    login(client, "learner")
    assert client.get(path).json()["goal"] == body["goal"]
    assert client.get("/api/v1/cases/" + scenario["case"]).json()["display_status"] == "training"
    assert client.get("/api/v1/sop-plans/" + plan["id"]).json()["draft_revision_id"] is None


def test_drafts_private_invalid_steps_and_active_task_rollback(client, scenario):
    headers, plan, path = setup_plan(client, scenario)
    login(client, "learner")
    assert client.get(path).status_code == 404
    assert client.get("/api/v1/cases/" + scenario["case"] + "/sop-plans").json()["items"] == []
    headers = login(client)
    body = content()
    body["steps"].append({**body["steps"][0]})
    assert client.put(path, headers={**headers, "If-Match": '"1"'}, json=body).status_code == 422
    assert (
        client.post(
            path + "/publish",
            headers={**headers, "If-Match": '"1"', "Idempotency-Key": str(uuid4())},
            json={"due_on": None},
        ).status_code
        == 422
    )
    body = content()
    client.put(path, headers={**headers, "If-Match": '"1"'}, json=body)
    assert (
        client.post(
            path + "/publish",
            headers={**headers, "If-Match": '"2"', "Idempotency-Key": str(uuid4())},
            json={"due_on": None},
        ).status_code
        == 200
    )
    revisions = "/api/v1/sop-plans/" + plan["id"] + "/revisions"
    r = client.post(
        revisions,
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"base_revision_id": plan["draft_revision_id"]},
    )
    assert r.status_code == 201 and r.json()["revision_no"] == 2
    draft = "/api/v1/sop-revisions/" + r.json()["id"]
    assert (
        client.post(
            revisions, headers={**headers, "Idempotency-Key": str(uuid4())}, json={}
        ).status_code
        == 409
    )
    assert (
        client.post(
            draft + "/publish",
            headers={**headers, "If-Match": '"1"', "Idempotency-Key": str(uuid4())},
            json={"due_on": None},
        ).status_code
        == 409
    )
    assert client.get(draft).json()["state"] == "draft"
    login(client, "outsider")
    assert client.get(path).status_code == 404
