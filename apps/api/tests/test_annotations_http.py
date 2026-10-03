from uuid import uuid4

import pytest
import test_cases_http as fixtures
from app.infrastructure.models import FileAsset
from test_cases_http import login
from test_training_http import change, setup_task, submit

pytestmark = pytest.mark.postgres
database = fixtures.database
db = fixtures.db
client = fixtures.client
scenario = fixtures.scenario


def test_draft_privacy_geometry_and_atomic_feedback_publication(db, client, scenario):
    path, steps = setup_task(client, scenario, 1)
    task_id = path.rsplit("/", 1)[1]
    headers = login(client, "learner")
    change(client, path, headers, 1, "start")
    with db.transaction() as s:
        asset = FileAsset(
            case_id=scenario["case"],
            task_id=task_id,
            uploader_id=scenario["learner"],
            purpose="task_evidence",
            filename="evidence.png",
            mime_type="image/png",
            size_bytes=100,
            sha256="a" * 64,
            storage_key="quarantine/" + uuid4().hex,
            state="ready",
            width=64,
            height=48,
        )
        s.add(asset)
        s.flush()
        asset_id = str(asset.id)
    result = client.put(
        path + "/steps/" + steps[0]["id"],
        headers={**headers, "If-Match": '"2"'},
        json={"status": "completed", "attachment_ids": [asset_id]},
    )
    assert result.status_code == 200
    submission = submit(client, path, headers, 3).json()
    headers = login(client)
    marker = dict(
        id=str(uuid4()), shape="rect", x=0.8, y=0.2, width=0.4, height=0.2, text="请核对文件名"
    )
    body = dict(
        asset_id=asset_id, submission_id=submission["id"], kind="guidance", markers=[marker]
    )
    assert (
        client.post(
            path + "/annotations", headers={**headers, "Idempotency-Key": str(uuid4())}, json=body
        ).status_code
        == 422
    )
    body["markers"][0]["x"] = 0.2
    created = client.post(
        path + "/annotations", headers={**headers, "Idempotency-Key": str(uuid4())}, json=body
    )
    assert created.status_code == 201, created.text
    annotation_id = created.json()["id"]
    login(client, "learner")
    assert client.get("/api/v1/annotations/" + annotation_id).status_code == 404
    assert client.get(path + "/annotations").json()["items"] == []
    headers = login(client)
    feedback = dict(
        outcome="changes_requested",
        message="请调整文件名",
        redo_step_ids=[steps[0]["id"]],
        annotation_ids=[annotation_id],
        tags=["naming_adjustment"],
    )
    review_path = "/api/v1/submissions/" + submission["id"] + "/feedback"
    r = client.post(
        review_path,
        headers={**headers, "If-Match": '"3"', "Idempotency-Key": str(uuid4())},
        json=feedback,
    )
    assert r.status_code == 412
    assert client.get("/api/v1/annotations/" + annotation_id).json()["state"] == "draft"
    r = client.post(
        review_path,
        headers={**headers, "If-Match": '"4"', "Idempotency-Key": str(uuid4())},
        json=feedback,
    )
    assert r.status_code == 201, r.text
    headers = login(client, "learner")
    assert client.get("/api/v1/annotations/" + annotation_id).json()["state"] == "published"
    headers = login(client)
    assert (
        client.put(
            "/api/v1/annotations/" + annotation_id,
            headers={**headers, "If-Match": '"2"'},
            json={"markers": body["markers"]},
        ).status_code
        == 409
    )
    login(client, "outsider")
    assert client.get("/api/v1/annotations/" + annotation_id).status_code == 404
