from io import BytesIO
from uuid import UUID, uuid4

import pytest
import test_cases_http as fixtures
from app.core.errors import AppError
from app.infrastructure.assets import require_files
from app.infrastructure.file_jobs import FileJobs
from app.infrastructure.models import AuditEvent, FileAsset, Job
from app.infrastructure.storage import LocalBlobStore
from app.worker import build_handlers
from PIL import Image
from sqlalchemy import select
from test_cases_http import login

pytestmark = pytest.mark.postgres
database = fixtures.database
db = fixtures.db
client = fixtures.client
scenario = fixtures.scenario


def picture():
    buffer = BytesIO()
    Image.new("RGB", (64, 48), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


class ScanUnavailable:
    def scan(self, source):
        raise AppError(503, "SCAN_UNAVAILABLE", "检测服务暂不可用")


class CleanScanner:
    # Unit test double only; runtime always uses the ClamAV adapter.
    def scan(self, source):
        return "clean"


def test_private_upload_replay_scan_gate_and_authorized_stream(db, client, scenario, tmp_path):
    client.app.state.settings.storage_root = tmp_path
    headers = login(client, "learner")
    command = {**headers, "Idempotency-Key": str(uuid4())}
    data = {"case_id": scenario["case"], "purpose": "profile_material"}
    content = picture()
    result = client.post(
        "/api/v1/files",
        headers=command,
        data=data,
        files={"file": ("资料.png", content, "image/png")},
    )
    assert result.status_code == 202, result.text
    asset = result.json()
    path = "/api/v1/files/" + asset["id"]
    assert "storage_key" not in asset and asset["state"] == "quarantined"
    assert (
        client.post(
            "/api/v1/files",
            headers=command,
            data=data,
            files={"file": ("资料.png", content, "image/png")},
        ).json()
        == asset
    )
    assert len(list((tmp_path / "quarantine").iterdir())) == 1
    assert client.get(path + "/content").status_code == 409
    blob = LocalBlobStore(tmp_path)
    with pytest.raises(AppError):
        FileJobs(db, blob, ScanUnavailable()).scan({"asset_id": asset["id"]})
    assert client.get(path).json()["state"] == "quarantined"
    headers = login(client)
    assert client.get(path).status_code == 404
    FileJobs(db, blob, CleanScanner()).scan({"asset_id": asset["id"]})
    metadata = client.get(path).json()
    assert metadata["state"] == "ready" and metadata["width"] == 64 and metadata["height"] == 48
    stream = client.get(path + "/content")
    assert stream.status_code == 200 and stream.content == content
    assert stream.headers["content-type"] == "image/png"
    assert "UTF-8" in stream.headers["content-disposition"]
    assert client.delete(path, headers={**headers, "If-Match": '"2"'}).status_code == 403
    headers = login(client, "learner")
    assert client.delete(path, headers={**headers, "If-Match": '"1"'}).status_code == 412
    assert client.delete(path, headers={**headers, "If-Match": '"2"'}).status_code == 204
    FileJobs(db, blob, CleanScanner()).scan({"asset_id": asset["id"]})
    FileJobs(db, blob, CleanScanner()).delete({"asset_id": asset["id"]})
    assert client.get(path).status_code == 404 and not list((tmp_path / "quarantine").iterdir())
    with db.transaction() as s:
        assert len(list(s.scalars(select(Job).where(Job.kind == "files.scan")))) == 1
        audits = list(s.scalars(select(AuditEvent).where(AuditEvent.resource_id == asset["id"])))
        assert {audit.action for audit in audits} == {"files.uploaded", "files.deleted"}
        assert len(audits) == 2 and all(audit.trace_id for audit in audits)


def test_reject_disguised_file_empty_foreign_scope_and_wrong_role(client, scenario, tmp_path):
    client.app.state.settings.storage_root = tmp_path
    headers = login(client, "learner")

    def upload(case_id, purpose, content):
        return client.post(
            "/api/v1/files",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            data={"case_id": case_id, "purpose": purpose},
            files={"file": ("伪装.png", content, "image/png")},
        )

    assert (
        upload(scenario["case"], "profile_material", b'<svg onload="alert(1)"></svg>').status_code
        == 415
    )
    assert upload(scenario["case"], "profile_material", b"").status_code == 413
    assert upload(str(uuid4()), "profile_material", picture()).status_code == 404
    assert upload(scenario["case"], "sop_media", picture()).status_code == 403
    assert not list((tmp_path / "quarantine").iterdir())


def test_disabled_scan_rejects_upload_before_storage_or_enqueue(db, client, scenario, tmp_path):
    client.app.state.settings.storage_root = tmp_path
    client.app.state.settings.scan_enabled = False
    headers = login(client, "learner")
    assert client.get("/api/v1/health/ready").status_code == 200
    result = client.post(
        "/api/v1/files",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        data={"case_id": scenario["case"], "purpose": "profile_material"},
        files={"file": ("资料.png", picture(), "image/png")},
    )
    assert result.status_code == 503, result.text
    assert result.json()["code"] == "SCAN_UNAVAILABLE"
    assert "上传暂不可用" in result.json()["title"]
    assert list(tmp_path.iterdir()) == []
    with db.transaction() as s:
        assert not list(s.scalars(select(FileAsset)))
        assert not list(s.scalars(select(Job).where(Job.kind == "files.scan")))


def test_disabled_scan_preserves_existing_file_gates_and_ready_authorization(
    db, client, scenario, tmp_path
):
    config = client.app.state.settings
    config.storage_root = tmp_path
    headers = login(client, "learner")
    assets = []
    for _ in range(2):
        result = client.post(
            "/api/v1/files",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            data={"case_id": scenario["case"], "purpose": "profile_material"},
            files={"file": ("资料.png", picture(), "image/png")},
        )
        assert result.status_code == 202
        assets.append(result.json()["id"])
    # Only the explicit unit-test scanner creates an existing ready asset.
    FileJobs(db, LocalBlobStore(tmp_path), CleanScanner()).scan({"asset_id": assets[1]})
    config.scan_enabled = False
    with pytest.raises(AppError) as error:
        build_handlers(db, config)["files.scan"]({"asset_id": assets[0]})
    assert error.value.code == "SCAN_UNAVAILABLE"
    pending, ready = ["/api/v1/files/" + value for value in assets]
    assert client.get(pending).json()["state"] == "quarantined"
    assert client.get(pending + "/content").json()["code"] == "FILE_NOT_READY"
    with db.transaction() as s, pytest.raises(AppError) as error:
        require_files(s, [UUID(assets[0])], UUID(scenario["case"]), "profile_material")
    assert error.value.code == "FILE_NOT_READY"
    assert client.get(ready + "/content").content == picture()
    login(client, "counselor")
    assert client.get(pending + "/content").status_code == 404
    assert client.get(ready + "/content").status_code == 200
    login(client, "outsider")
    assert client.get(ready + "/content").status_code == 404
    client.cookies.clear()
    assert client.get(ready + "/content").status_code == 401
