from uuid import uuid4

import pytest
import test_cases_http as fixtures
from test_cases_http import login
from test_training_http import setup_task

pytestmark = pytest.mark.postgres
database = fixtures.database
db = fixtures.db
client = fixtures.client
scenario = fixtures.scenario


def test_help_message_accept_resolve_and_owned_notifications(client, scenario):
    task, steps = setup_task(client, scenario, 1)
    headers = login(client, "learner")
    body = dict(
        case_id=scenario["case"],
        task_id=task.rsplit("/", 1)[1],
        step_id=steps[0]["id"],
        message="这一步需要文字提示",
        attachment_ids=[],
        preferred_mode="text",
    )
    command = {**headers, "Idempotency-Key": str(uuid4())}
    result = client.post("/api/v1/assistance-requests", headers=command, json=body)
    assert result.status_code == 201, result.text
    assert (
        client.post("/api/v1/assistance-requests", headers=command, json=body).json()
        == result.json()
    )
    assert (
        client.post(
            "/api/v1/assistance-requests",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json=body,
        ).status_code
        == 409
    )
    path = "/api/v1/assistance-requests/" + result.json()["id"]
    assert client.get(path).json()["state"] == "queued"
    r = client.post(
        path + "/messages",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"body": "我想先核对文件名", "attachment_ids": []},
    )
    assert r.status_code == 201
    headers = login(client)
    notifications = client.get("/api/v1/notifications").json()["items"]
    assert any(n["type"] == "support.requested" for n in notifications)
    notification = notifications[0]["id"]
    read = client.post(
        "/api/v1/notifications/" + notification + "/read",
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert read.status_code == 204 and not read.content
    for version, action in [(1, "accept"), (2, "resolve")]:
        r = client.post(
            path + "/actions",
            headers={**headers, "If-Match": f'"{version}"', "Idempotency-Key": str(uuid4())},
            json={"action": action},
        )
        assert r.status_code == 200, r.text
    assert (
        client.post(
            path + "/messages",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"body": "关闭后不能追加", "attachment_ids": []},
        ).status_code
        == 409
    )
    assert len(client.get(path + "/messages").json()["items"]) == 1
    headers = login(client, "learner")
    assert (
        client.post(
            "/api/v1/notifications/" + notification + "/read",
            headers={**headers, "Idempotency-Key": str(uuid4())},
        ).status_code
        == 404
    )
    records = client.get("/api/v1/cases/" + scenario["case"] + "/records").json()
    assert records["items"][0]["assistance_requests"] == 1
    login(client, "outsider")
    assert client.get(path).status_code == 404
    assert client.get("/api/v1/assistance-requests").json()["items"] == []


def test_prompt_override_is_versioned_scoped_and_never_advances_steps(client, scenario):
    task, steps = setup_task(client, scenario, 1)
    headers = login(client, "learner")
    body = {"prompt_level": 3, "reason": "沟通后增加提示"}
    assert (
        client.put(
            task + "/prompt-override", headers={**headers, "If-Match": '"1"'}, json=body
        ).status_code
        == 403
    )
    headers = login(client)
    r = client.put(task + "/prompt-override", headers={**headers, "If-Match": '"1"'}, json=body)
    assert r.status_code == 200 and r.json()["version"] == 2, r.text
    assert r.json()["progress"][0]["status"] == "pending"
    assert (
        client.put(
            task + "/prompt-override", headers={**headers, "If-Match": '"1"'}, json=body
        ).status_code
        == 412
    )
    assert (
        client.put(task + "/prompt-override", headers={"If-Match": '"2"'}, json=body).status_code
        == 403
    )
