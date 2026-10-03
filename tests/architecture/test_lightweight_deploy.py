from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_private_volume_is_project_scoped_and_only_mounted_by_api_and_worker():
    compose = yaml.safe_load((ROOT / "infra/compose.production.yaml").read_text())
    assert compose["volumes"]["private-files"] is None
    assert set(compose["services"]) == {"db", "migrate", "api", "worker", "gateway"}
    for name, service in compose["services"].items():
        mounts = service.get("volumes", [])
        if name in {"api", "worker"}:
            assert "private-files:/srv/.data/private" in mounts
            env = service["environment"]
            assert env["JOB_LENS_STORAGE_KIND"] == "${JOB_LENS_STORAGE_KIND:-s3}"
            assert env["JOB_LENS_STORAGE_ROOT"] == "/srv/.data/private"
            assert env["JOB_LENS_S3_BUCKET"] == "${JOB_LENS_S3_BUCKET:-}"
            assert env["JOB_LENS_SCAN_ENABLED"] == "${JOB_LENS_SCAN_ENABLED:-true}"
        else:
            assert not any("private-files" in mount for mount in mounts)


def dependency_preflight():
    script = (ROOT / "tools/deploy_joblens.sh").read_text()
    return script.split("<<'PYCODE'\n", 1)[1].split("\nPYCODE", 1)[0]


@pytest.mark.parametrize("enabled", [False, True])
def test_deployment_requires_scanner_only_when_uploads_are_enabled(enabled, capsys):
    cfg = SimpleNamespace(scan_enabled=enabled, scan_host="test-scanner", scan_port=3310)
    with (
        patch("app.core.config.Settings", return_value=cfg),
        patch("app.infrastructure.email.require_delivery") as mail,
        patch("socket.create_connection") as connect,
    ):
        connect.return_value.__enter__.return_value.recv.return_value = b"PONG\0"
        exec(dependency_preflight(), {})
        mail.assert_called_once_with(cfg)
        if enabled:
            connect.assert_called_once_with(("test-scanner", 3310), timeout=5)
        else:
            connect.assert_not_called()
            assert "uploads unavailable" in capsys.readouterr().out


def test_enabled_scan_preflight_still_fails_closed():
    cfg = SimpleNamespace(scan_enabled=True, scan_host="test-scanner", scan_port=3310)
    with (
        patch("app.core.config.Settings", return_value=cfg),
        patch("app.infrastructure.email.require_delivery"),
        patch("socket.create_connection", side_effect=OSError("offline")),
        pytest.raises(SystemExit) as failure,
    ):
        exec(dependency_preflight(), {})
    assert failure.value.code == 1
