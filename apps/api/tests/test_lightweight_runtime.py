from pathlib import Path
from unittest.mock import patch

import pytest
from app.core.config import Settings

URL = "postgresql+psycopg://test@localhost/job_lens_test"


def production(**overrides):
    return Settings(
        database_url=URL,
        environment="production",
        public_origin="https://job-lens.example.invalid",
        **overrides,
        _env_file=None,
    )


def test_production_local_storage_is_explicit_and_scan_defaults_to_enabled(tmp_path):
    config = production(storage_kind="local", storage_root=tmp_path)
    assert config.storage_kind == "local"
    assert config.scan_enabled is True
    assert production(storage_root=tmp_path, scan_enabled=False).scan_enabled is False


def test_production_keeps_https_and_rejects_relative_local_storage(tmp_path):
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(
            database_url=URL,
            environment="production",
            storage_root=tmp_path,
            scan_enabled=False,
            _env_file=None,
        )
    with pytest.raises(ValueError, match="absolute"):
        production(storage_kind="local", storage_root=Path(".data/private"))


def test_production_s3_remains_available_and_requires_a_bucket():
    assert production(storage_kind="s3", s3_bucket="private-test-bucket").storage_kind == "s3"
    with pytest.raises(ValueError, match="s3_bucket"):
        production(storage_kind="s3")


def test_existing_s3_and_real_scanner_wiring_is_preserved():
    from app.infrastructure.scanning import ClamAVScanner
    from app.worker import build_handlers

    config = production(storage_kind="s3", s3_bucket="private-test-bucket")
    with patch("app.worker.S3BlobStore") as store, patch("app.worker.FileJobs") as jobs:
        build_handlers(object(), config)
        store.assert_called_once_with(config)
        assert jobs.call_args.args[1] is store.return_value
        assert isinstance(jobs.call_args.args[2], ClamAVScanner)


def test_scan_disable_uses_an_explicit_environment_value(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_LENS_SCAN_ENABLED", "false")
    assert production(storage_root=tmp_path).scan_enabled is False


def test_disabled_scan_handler_cannot_read_or_transmit_a_file(tmp_path):
    from app.core.errors import AppError
    from app.worker import build_handlers

    config = production(storage_root=tmp_path, scan_enabled=False)
    with patch("app.worker.FileJobs") as jobs, patch("socket.create_connection") as connect:
        build_handlers(object(), config)
        scanner = jobs.call_args.args[2]
        with pytest.raises(AppError) as error:
            scanner.scan(object())
        assert error.value.status == 503 and error.value.code == "SCAN_UNAVAILABLE"
        connect.assert_not_called()
