from uuid import uuid4

import pytest
import test_cases_http as fixtures
from test_cases_http import login
from test_sop_http import content, setup_plan

pytestmark = pytest.mark.postgres
database = fixtures.database
db = fixtures.db
client = fixtures.client
scenario = fixtures.scenario


def setup_task(client, scenario, count=2):
    headers, plan, revision = setup_plan(client, scenario)
    body = content()
    for pos in range(2, count + 1):
        body["steps"].append(
            {**body["steps"][0], "id": str(uuid4()), "position": pos, "instruction": "按日期归档"}
        )
    assert (
        client.put(revision, headers={**headers, "If-Match": '"1"'}, json=body).status_code == 200
    )
    pub = client.post(
        revision + "/publish",
        headers={**headers, "If-Match": '"2"', "Idempotency-Key": str(uuid4())},
        json={"due_on": None},
    )
    assert pub.status_code == 200
    path = "/api/v1/tasks/" + pub.json()["task_id"]
    return path, body["steps"]


def change(client, path, headers, version, action):
    return client.post(
        path + "/actions",
        headers={**headers, "If-Match": f'"{version}"', "Idempotency-Key": str(uuid4())},
        json={"action": action},
    )


def finish(client, path, headers, version, step):
    return client.put(
        path + "/steps/" + step["id"],
        headers={**headers, "If-Match": f'"{version}"'},
        json={"status": "completed", "attachment_ids": []},
    )


def submit(client, path, headers, version, key=None):
    return client.post(
        path + "/submissions",
        headers={**headers, "If-Match": f'"{version}"', "Idempotency-Key": key or str(uuid4())},
        json={"note": "已按步骤整理"},
    )


def test_complete_rework_resubmit_pass_and_immutable_history(client, scenario):
    path, steps = setup_task(client, scenario)
    headers = login(client, "learner")
    assert client.get("/api/v1/tasks").json()["items"][0]["id"] == path.rsplit("/", 1)[1]
    assert change(client, path, headers, 1, "start").json()["version"] == 2
    assert submit(client, path, headers, 2).status_code == 409
    assert finish(client, path, headers, 2, steps[1]).status_code == 409
    assert finish(client, path, headers, 2, steps[0]).json()["version"] == 3
    assert change(client, path, headers, 3, "pause").json()["status"] == "paused"
    assert finish(client, path, headers, 4, steps[1]).status_code == 409
    assert change(client, path, headers, 4, "resume").json()["version"] == 5
    assert finish(client, path, headers, 5, steps[1]).json()["version"] == 6
    key = str(uuid4())
    first = submit(client, path, headers, 6, key)
    assert first.status_code == 201, first.text
    assert submit(client, path, headers, 6, key).json() == first.json()
    submission = "/api/v1/submissions/" + first.json()["id"]
    frozen = first.json()["snapshot"]
    feedback = {
        "outcome": "changes_requested",
        "message": "第二步请按日期重新归档",
        "redo_step_ids": [steps[1]["id"]],
        "annotation_ids": [],
        "tags": ["naming_adjustment"],
    }
    assert (
        client.post(
            submission + "/feedback",
            headers={**headers, "If-Match": '"7"', "Idempotency-Key": str(uuid4())},
            json=feedback,
        ).status_code
        == 403
    )
    headers = login(client)
    command = {**headers, "If-Match": '"7"', "Idempotency-Key": str(uuid4())}
    result = client.post(submission + "/feedback", headers=command, json=feedback)
    assert result.status_code == 201, result.text
    assert (
        client.post(submission + "/feedback", headers=command, json=feedback).json()
        == result.json()
    )
    progress = result.json()["task"]["progress"]
    assert [p["status"] for p in progress] == ["completed", "pending"]
    assert client.get(submission).json()["snapshot"] == frozen
    headers = login(client, "learner")
    assert change(client, path, headers, 8, "resume").json()["version"] == 9
    assert client.get(path).json()["current_step_id"] == steps[1]["id"]
    assert finish(client, path, headers, 9, steps[1]).json()["version"] == 10
    second = submit(client, path, headers, 10)
    assert second.json()["attempt_no"] == 2
    headers = login(client)
    feedback = {**feedback, "outcome": "passed", "message": "文件整理完成", "redo_step_ids": []}
    done = client.post(
        "/api/v1/submissions/" + second.json()["id"] + "/feedback",
        headers={**headers, "If-Match": '"11"', "Idempotency-Key": str(uuid4())},
        json=feedback,
    )
    assert done.status_code == 201 and done.json()["task"]["status"] == "completed"
    assert change(client, path, headers, 12, "cancel").status_code == 422
    record = client.get("/api/v1/cases/" + scenario["case"] + "/records").json()["items"][0]
    assert record["attempts"] == 2 and record["status"] == "completed"
    assert record["observed_elapsed_ms"] is None
    login(client, "outsider")
    assert client.get(path).status_code == 404 and client.get(submission).status_code == 404


def test_observation_dedup_never_completes_and_scope_version_guards(client, scenario):
    path, steps = setup_task(client, scenario, 1)
    headers = login(client, "learner")
    change(client, path, headers, 1, "start")
    event = {
        "event_id": str(uuid4()),
        "session_id": str(uuid4()),
        "sequence": 1,
        "step_id": steps[0]["id"],
        "kind": "hint_requested",
        "value": 0,
        "observed_at": "2026-10-02T12:00:00Z",
    }
    r = client.post(
        path + "/events",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"events": [event, event]},
    )
    assert r.status_code == 200 and r.json() == {"accepted": 1, "duplicates": 1}
    assert client.get(path).json()["progress"][0]["status"] == "pending"
    r = client.post(
        path + "/events",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"events": [{**event, "value": 1}]},
    )
    assert r.status_code == 409
    assert finish(client, path, headers, 1, steps[0]).status_code == 412
    assert client.get("/api/v1/tasks?status=not_started").json()["items"] == []
    assert client.get("/api/v1/tasks?cursor=bad").status_code == 400
    assert (
        client.get("/api/v1/cases/" + scenario["case"] + "/records").json()["items"][0][
            "hint_requests"
        ]
        == 1
    )
