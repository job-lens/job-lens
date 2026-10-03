"""Operator CLI behavior with a mocked database; these tests provision no real accounts."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.infrastructure.db import utcnow
from app.modules.identity.models import AdministratorGrant, ManagementEvent

from tools import manage_administrator as cli


@pytest.fixture
def operator(monkeypatch):
    user = SimpleNamespace(id=uuid4(), active=True, credential_version=4)
    session = MagicMock()
    session.scalar.return_value = user
    session.get.return_value = None
    database = MagicMock()
    database.transaction.return_value.__enter__.return_value = session
    connect = MagicMock(return_value=database)
    monkeypatch.setattr(cli.Database, "from_settings", connect)
    monkeypatch.setattr(cli, "Settings", MagicMock())

    def invoke(*options, reason="Approved operator change ticket", user_id=None):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "manage_administrator.py",
                "--user-id",
                str(user_id or user.id),
                "--reason",
                reason,
                *options,
            ],
        )
        cli.main()

    return SimpleNamespace(
        user=user, session=session, database=database, connect=connect, invoke=invoke
    )


@pytest.mark.parametrize("revoke", [False, True])
def test_operator_defaults_to_dry_run_without_writes(operator, capsys, revoke):
    grant = AdministratorGrant(user_id=operator.user.id, granted_at=utcnow()) if revoke else None
    operator.session.get.return_value = grant
    operator.invoke(*(["--revoke"] if revoke else []))
    assert "Dry run only" in capsys.readouterr().out
    operator.session.add.assert_not_called()
    assert operator.session.execute.call_count == 1  # Advisory lock only.
    assert operator.user.credential_version == 4
    if grant:
        assert grant.revoked_at is None
    operator.database.close.assert_called_once()


@pytest.mark.parametrize("existing", [False, True])
def test_apply_grant_updates_mock_account_and_writes_operator_audit(operator, capsys, existing):
    old = utcnow()
    grant = (
        AdministratorGrant(user_id=operator.user.id, granted_at=old, revoked_at=old)
        if existing
        else None
    )
    operator.session.get.return_value = grant
    operator.invoke("--apply", reason="  Approved operator change ticket  ")
    added = [call.args[0] for call in operator.session.add.call_args_list]
    grants = [row for row in added if isinstance(row, AdministratorGrant)]
    if existing:
        assert grants == []
        assert grant.revoked_at is None and grant.granted_at >= old
    else:
        assert len(grants) == 1 and grants[0].user_id == operator.user.id
        assert grants[0].granted_at is not None and grants[0].revoked_at is None
    event = next(row for row in added if isinstance(row, ManagementEvent))
    assert event.actor_id is None
    assert event.target_id == operator.user.id
    assert event.action == "identity.operator_admin_granted"
    assert event.reason == "Approved operator change ticket"
    assert len(event.trace_id) == 32
    assert operator.user.credential_version == 5
    assert "Applied" in capsys.readouterr().out
    operator.database.close.assert_called_once()


def test_apply_revoke_allows_inactive_mock_account_and_invalidates_cookies(operator):
    operator.user.active = False
    grant = AdministratorGrant(user_id=operator.user.id, granted_at=utcnow())
    operator.session.get.return_value = grant
    operator.invoke("--revoke", "--apply")
    assert grant.revoked_at is not None
    assert operator.user.credential_version == 5
    added = [call.args[0] for call in operator.session.add.call_args_list]
    assert len(added) == 1 and isinstance(added[0], ManagementEvent)
    assert added[0].action == "identity.operator_admin_revoked"
    assert added[0].target_id == operator.user.id
    operator.database.close.assert_called_once()


@pytest.mark.parametrize("revoke", [False, True])
def test_apply_does_not_repeat_already_satisfied_change(operator, capsys, revoke):
    operator.session.get.return_value = (
        None if revoke else AdministratorGrant(user_id=operator.user.id, granted_at=utcnow())
    )
    operator.invoke("--apply", *(["--revoke"] if revoke else []))
    assert "No change required" in capsys.readouterr().out
    operator.session.add.assert_not_called()
    assert operator.user.credential_version == 4
    operator.database.close.assert_called_once()


@pytest.mark.parametrize("target", ["missing", "inactive"])
def test_operator_cannot_grant_missing_or_inactive_mock_account(operator, target):
    if target == "missing":
        operator.session.scalar.return_value = None
    else:
        operator.user.active = False
    with pytest.raises(SystemExit, match="existing active account"):
        operator.invoke("--apply")
    operator.session.add.assert_not_called()
    assert operator.user.credential_version == 4
    operator.database.close.assert_called_once()


@pytest.mark.parametrize("reason", ["", "  ", "x" * 1001])
def test_operator_rejects_invalid_reason_before_connecting(operator, reason):
    with pytest.raises(SystemExit) as error:
        operator.invoke("--apply", reason=reason)
    assert error.value.code == 2
    operator.connect.assert_not_called()


def test_operator_rejects_invalid_account_id_before_connecting(operator):
    with pytest.raises(SystemExit) as error:
        operator.invoke("--apply", user_id="not-a-uuid")
    assert error.value.code == 2
    operator.connect.assert_not_called()
