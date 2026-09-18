import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import database_backup as tool


def fake_dump(command, *args, **kwargs):
    kwargs["stdout"].write(b"PGDMP-test-only-archive")


def test_backup_is_private_and_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "compose", fake_dump)
    target = tmp_path / "db.dump"
    tool.backup(target)
    assert target.stat().st_mode & 0o777 == 0o600
    assert Path(str(target) + ".sha256").read_text().strip() == tool.checksum(target)
    with pytest.raises(FileExistsError):
        tool.backup(target)


def test_failed_backup_removes_partial_archive(tmp_path, monkeypatch):
    def failed(*args, **kwargs):
        kwargs["stdout"].write(b"partial")
        raise subprocess.CalledProcessError(1, ["pg_dump"])

    monkeypatch.setattr(tool, "compose", failed)
    target = tmp_path / "db.dump"
    with pytest.raises(subprocess.CalledProcessError):
        tool.backup(target)
    assert not target.exists()


def test_checksum_failure_does_not_touch_database(tmp_path, monkeypatch):
    target = tmp_path / "db.dump"
    target.write_bytes(b"changed")
    Path(str(target) + ".sha256").write_text("wrong")
    monkeypatch.setattr(tool, "compose", lambda *a, **k: pytest.fail("must not reach DB"))
    with pytest.raises(ValueError, match="checksum"):
        tool.verify(target)


@pytest.mark.parametrize("fails", [False, True])
def test_restore_uses_new_database_and_always_cleans_it(tmp_path, monkeypatch, fails):
    target = tmp_path / "db.dump"
    target.write_bytes(b"PGDMP-test")
    Path(str(target) + ".sha256").write_text(tool.checksum(target))
    calls = []

    def run(command, *args, **kwargs):
        calls.append((command, args))
        if "pg_restore" in command and fails:
            raise subprocess.CalledProcessError(1, ["pg_restore"])
        return SimpleNamespace(stdout="0002_integrity\n1\n")

    monkeypatch.setattr(tool, "compose", run)
    if fails:
        with pytest.raises(subprocess.CalledProcessError):
            tool.verify(target)
    else:
        assert "jobs=1" in tool.verify(target)
    database = calls[0][1][0]
    assert database.startswith("job_lens_restore_") and database.endswith("_test")
    assert all(args == (database,) for _, args in calls)
    assert "createdb" in calls[0][0] and "dropdb" in calls[-1][0]
