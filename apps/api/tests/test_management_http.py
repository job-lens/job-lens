"""Administrative HTTP boundaries using grants confined to the disposable test DB."""

from uuid import uuid4

import pytest
import test_postgres as postgres_fixtures
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import hash_password
from app.core.types import Actor
from app.infrastructure.db import utcnow
from app.main import create_app
from app.modules.cases.models import Case, CaseGrant, SupportMatch
from app.modules.identity.models import (
    AdministratorGrant,
    CounselorCertification,
    Preferences,
    Profile,
    SessionRecord,
    User,
    UserRole,
)
from app.modules.identity.queries import is_administrator, require_administrator
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.postgres
database = postgres_fixtures.database
db = postgres_fixtures.db


@pytest.fixture
def scenario(db):
    with db.transaction() as session:
        users = {}
        password_hash = hash_password("training-password")
        for name, role, active in [
            ("admin", "learner", True),
            ("learner", "learner", True),
            ("counselor", "counselor", True),
            ("certified", "counselor", True),
            ("inactive", "counselor", False),
        ]:
            user = User(login_name=name, password_hash=password_hash, active=active)
            session.add(user)
            session.flush()
            session.add_all(
                [
                    UserRole(user_id=user.id, role=role),
                    Profile(
                        user_id=user.id,
                        display_name=name,
                        work_notes="Private learner information",
                    ),
                    Preferences(user_id=user.id),
                ]
            )
            users[name] = user.id
        # Only test fixtures grant administration. Ordinary user roles do not grant it.
        session.add(AdministratorGrant(user_id=users["admin"], granted_at=utcnow()))
        for name in ("certified", "inactive"):
            session.add(
                CounselorCertification(
                    user_id=users[name],
                    state="approved",
                    statement="Training and experience reviewed in this test fixture.",
                    reason="Test fixture approval",
                    reviewer_id=users["admin"],
                    reviewed_at=utcnow(),
                )
            )
        for key, learner in [("case", "learner"), ("own_case", "admin")]:
            case = Case(learner_id=users[learner])
            session.add(case)
            session.flush()
            session.add(SupportMatch(case_id=case.id))
            users[key] = case.id
        return users


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


def login(client, name="admin"):
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    result = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://testserver", "X-CSRF-Token": csrf},
        json={"login_name": name, "password": "training-password"},
    )
    assert result.status_code == 200, result.text
    return {"Origin": "https://testserver", "X-CSRF-Token": result.json()["csrf_token"]}


def versioned(headers, version=1):
    return {**headers, "If-Match": f'"{version}"'}


def admin_requests(scenario):
    return [
        ("GET", "/api/v1/admin/users", None),
        ("GET", "/api/v1/admin/audit", None),
        (
            "PUT",
            f"/api/v1/admin/users/{scenario['learner']}/status",
            {"active": False, "reason": "Account review"},
        ),
        ("GET", "/api/v1/admin/counselor-certifications", None),
        (
            "PUT",
            f"/api/v1/admin/counselor-certifications/{scenario['learner']}",
            {"decision": "approved", "reason": "Verified qualifications"},
        ),
        ("GET", "/api/v1/admin/cases", None),
        (
            "PUT",
            f"/api/v1/admin/cases/{scenario['case']}/counselors/{scenario['certified']}",
            {"assigned": True, "reason": "Approved support assignment"},
        ),
    ]


def submit_application(client, name="learner"):
    headers = login(client, name)
    path = "/api/v1/me/counselor-certification"
    current = client.get(path)
    result = client.put(
        path,
        headers={**headers, "If-Match": current.headers["etag"]},
        json={"statement": "I have completed the counselor training program."},
    )
    assert result.status_code == 200, result.text
    return result


def test_all_management_routes_require_authentication(client, scenario):
    requests = admin_requests(scenario) + [
        ("GET", "/api/v1/me/administration", None),
        ("GET", "/api/v1/me/counselor-certification", None),
        (
            "PUT",
            "/api/v1/me/counselor-certification",
            {"statement": "My training qualifications"},
        ),
    ]
    headers = versioned(
        {"Origin": "https://testserver", "X-CSRF-Token": "unauthenticated-csrf-token"}
    )
    for method, path, body in requests:
        response = client.request(method, path, headers=headers, json=body)
        assert response.status_code == 401, (method, path, response.text)


@pytest.mark.parametrize("name", ["learner", "counselor", "certified"])
def test_ordinary_roles_do_not_grant_administration(client, scenario, name):
    headers = login(client, name)
    assert client.get("/api/v1/me/administration").json() == {"can_manage_users": False}
    for method, path, body in admin_requests(scenario):
        result = client.request(method, path, headers=versioned(headers), json=body)
        assert result.status_code == 403, (method, path, result.text)


def test_admin_capability_is_separate_and_revocation_is_immediate(db, client, scenario):
    headers = login(client)
    assert client.get("/api/v1/me/administration").json() == {"can_manage_users": True}
    assert client.get("/api/v1/me").json()["roles"] == ["learner"]
    assert client.get("/api/v1/admin/users").status_code == 200
    with db.transaction() as session:
        session.get(AdministratorGrant, scenario["admin"]).revoked_at = utcnow()
    assert client.get("/api/v1/me/administration").json() == {"can_manage_users": False}
    for method, path, body in admin_requests(scenario):
        response = client.request(method, path, headers=versioned(headers), json=body)
        assert response.status_code == 403, (method, path, response.text)


def test_certification_submission_requires_csrf_and_current_version(client):
    headers = login(client, "learner")
    path = "/api/v1/me/counselor-certification"
    initial = client.get(path)
    assert initial.status_code == 200
    assert initial.headers["etag"] == '"1"'
    assert initial.json()["state"] == "not_submitted"
    assert initial.json()["reviewer_id"] is None
    assert initial.json()["reviewed_at"] is None
    body = {"statement": "Completed counselor training and supervised practice."}
    assert client.put(path, headers=headers, json=body).status_code == 428
    assert client.put(path, headers={"If-Match": '"1"'}, json=body).status_code == 403
    assert (
        client.put(
            path, headers={**versioned(headers), "Origin": "https://evil.test"}, json=body
        ).status_code
        == 403
    )
    assert client.get(path).json()["state"] == "not_submitted"
    submitted = client.put(path, headers=versioned(headers), json=body)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["state"] == "pending"
    assert submitted.json()["statement"] == body["statement"]
    assert submitted.json()["version"] == 2
    assert submitted.headers["etag"] == '"2"'
    assert client.put(path, headers=versioned(headers), json=body).status_code == 412
    assert client.get("/api/v1/me").json()["roles"] == ["learner"]


def test_review_approval_and_revocation_change_only_counselor_role(client, scenario):
    application = submit_application(client)
    headers = login(client)
    path = f"/api/v1/admin/counselor-certifications/{scenario['learner']}"
    pending = client.get("/api/v1/admin/counselor-certifications?state=pending").json()
    assert pending["total"] == 1
    assert pending["items"][0]["user_id"] == str(scenario["learner"])
    body = {"decision": "approved", "reason": "Training evidence verified"}
    review_headers = {**headers, "If-Match": application.headers["etag"]}
    assert client.put(path, headers=headers, json=body).status_code == 428
    assert (
        client.put(path, headers={"If-Match": application.headers["etag"]}, json=body).status_code
        == 403
    )
    approved = client.put(path, headers=review_headers, json=body)
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved"
    assert approved.json()["reason"] == body["reason"]
    assert approved.json()["reviewer_id"] == str(scenario["admin"])
    assert approved.json()["reviewed_at"] is not None
    assert approved.json()["version"] == 3
    assert client.put(path, headers=review_headers, json=body).status_code == 412
    login(client, "learner")
    assert set(client.get("/api/v1/me").json()["roles"]) == {"learner", "counselor"}
    assert client.get("/api/v1/me/administration").json() == {"can_manage_users": False}
    headers = login(client)
    revoked = client.put(
        path,
        headers={**headers, "If-Match": approved.headers["etag"]},
        json={"decision": "revoked", "reason": "Certification no longer valid"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["state"] == "revoked"
    login(client, "learner")
    assert client.get("/api/v1/me").json()["roles"] == ["learner"]
    assert client.get("/api/v1/me/counselor-certification").json()["state"] == "revoked"


def test_rejected_application_can_be_resubmitted_without_granting_role(client, scenario):
    application = submit_application(client)
    headers = login(client)
    result = client.put(
        f"/api/v1/admin/counselor-certifications/{scenario['learner']}",
        headers={**headers, "If-Match": application.headers["etag"]},
        json={"decision": "rejected", "reason": "Additional training evidence required"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["state"] == "rejected"
    resubmitted = submit_application(client)
    assert resubmitted.json()["state"] == "pending"
    assert resubmitted.json()["reviewer_id"] is None
    assert resubmitted.json()["reviewed_at"] is None
    assert client.get("/api/v1/me").json()["roles"] == ["learner"]


def test_administrator_cannot_review_self_change_own_status_or_assign_own_case(client, scenario):
    application = submit_application(client, "admin")
    headers = login(client)
    review = client.put(
        f"/api/v1/admin/counselor-certifications/{scenario['admin']}",
        headers={**headers, "If-Match": application.headers["etag"]},
        json={"decision": "approved", "reason": "Self approval must be blocked"},
    )
    assert review.status_code == 403
    status = client.put(
        f"/api/v1/admin/users/{scenario['admin']}/status",
        headers=versioned(headers),
        json={"active": False, "reason": "Self suspension must be blocked"},
    )
    assert status.status_code == 403
    own_case = client.put(
        f"/api/v1/admin/cases/{scenario['own_case']}/counselors/{scenario['certified']}",
        headers=versioned(headers),
        json={"assigned": True, "reason": "Own-case assignment must be blocked"},
    )
    assert own_case.status_code == 403
    self_assignment = client.put(
        f"/api/v1/admin/cases/{scenario['case']}/counselors/{scenario['admin']}",
        headers=versioned(headers),
        json={"assigned": True, "reason": "Self assignment must be blocked"},
    )
    assert self_assignment.status_code == 403
    assert client.get("/api/v1/me/counselor-certification").json()["state"] == "pending"
    assert client.get("/api/v1/me").status_code == 200


def test_admin_lists_are_paginated_and_do_not_expose_case_profiles(client, scenario):
    login(client)
    for path, total, key in [
        ("/api/v1/admin/users", 5, "id"),
        ("/api/v1/admin/cases", 2, "id"),
        ("/api/v1/admin/counselor-certifications", 2, "user_id"),
    ]:
        first = client.get(path, params={"limit": 1, "offset": 0})
        second = client.get(path, params={"limit": 1, "offset": 1})
        assert first.status_code == second.status_code == 200
        assert first.json()["total"] == second.json()["total"] == total
        assert len(first.json()["items"]) == len(second.json()["items"]) == 1
        assert first.json()["items"][0][key] != second.json()["items"][0][key]
        assert client.get(path, params={"limit": 1, "offset": 100}).json()["items"] == []
        assert client.get(path, params={"offset": -1}).status_code == 422
    assert client.get("/api/v1/admin/counselor-certifications?state=invalid").status_code == 422
    users = client.get("/api/v1/admin/users").json()["items"]
    for user in users:
        assert {"id", "display_name", "active", "roles", "version"} <= user.keys()
        assert (
            not {"password_hash", "login_name", "work_notes", "sensory_preferences"} & user.keys()
        )
    cases = client.get("/api/v1/admin/cases").json()["items"]
    assert any(row["id"] == str(scenario["case"]) for row in cases)
    for row in cases:
        assert {"id", "learner_id", "counselor_ids", "version"} <= row.keys()
        assert not {"profile", "work_notes", "sensory_preferences", "preferences"} & row.keys()
    # Administrative discovery must not become clinical/case content access.
    for suffix in ("", "/profile", "/match", "/materials"):
        assert client.get(f"/api/v1/cases/{scenario['case']}{suffix}").status_code == 404


def test_status_requires_csrf_and_version_and_suspension_invalidates_sessions(db, client, scenario):
    with TestClient(client.app, base_url="https://testserver") as learner_client:
        login(learner_client, "learner")
        assert learner_client.get("/api/v1/me").status_code == 200
        headers = login(client)
        path = f"/api/v1/admin/users/{scenario['learner']}/status"
        body = {"active": False, "reason": "Temporary account review"}
        assert client.put(path, headers=headers, json=body).status_code == 428
        assert client.put(path, headers={"If-Match": '"1"'}, json=body).status_code == 403
        suspended = client.put(path, headers=versioned(headers), json=body)
        assert suspended.status_code == 200, suspended.text
        assert suspended.json()["active"] is False
        assert suspended.json()["version"] == 2
        assert client.put(path, headers=versioned(headers), json=body).status_code == 412
        assert learner_client.get("/api/v1/me").status_code == 401
        with db.transaction() as session:
            sessions = session.scalars(
                select(SessionRecord).where(SessionRecord.user_id == scenario["learner"])
            ).all()
            current = session.get(User, scenario["learner"])
            assert sessions and all(
                row.credential_version != current.credential_version for row in sessions
            )
        restored = client.put(
            path,
            headers={**headers, "If-Match": suspended.headers["etag"]},
            json={"active": True, "reason": "Account review complete"},
        )
        assert restored.status_code == 200, restored.text
        assert learner_client.get("/api/v1/me").status_code == 401
        login(learner_client, "learner")
        assert learner_client.get("/api/v1/me").status_code == 200


def test_assignments_require_active_certified_counselor_and_current_version(db, client, scenario):
    headers = login(client)
    base = f"/api/v1/admin/cases/{scenario['case']}/counselors/"
    body = {"assigned": True, "reason": "Support coverage assignment"}
    for name, expected in [("learner", 403), ("counselor", 409), ("inactive", 409)]:
        result = client.put(base + str(scenario[name]), headers=versioned(headers), json=body)
        assert result.status_code == expected, (name, result.text)
    path = base + str(scenario["certified"])
    assert client.put(path, headers=headers, json=body).status_code == 428
    assert client.put(path, headers={"If-Match": '"1"'}, json=body).status_code == 403
    assigned = client.put(path, headers=versioned(headers), json=body)
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["version"] == 2
    assert str(scenario["certified"]) in assigned.json()["counselor_ids"]
    assert client.put(path, headers=versioned(headers), json=body).status_code == 412
    with db.transaction() as session:
        grant = session.get(CaseGrant, (scenario["case"], scenario["certified"]))
        assert grant is not None and grant.revoked_at is None
    login(client, "certified")
    assert client.get(f"/api/v1/cases/{scenario['case']}/profile").status_code == 200
    headers = login(client)
    revoked = client.put(
        path,
        headers={**headers, "If-Match": assigned.headers["etag"]},
        json={"assigned": False, "reason": "Support assignment ended"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["version"] == 3
    assert str(scenario["certified"]) not in revoked.json()["counselor_ids"]
    login(client, "certified")
    assert client.get(f"/api/v1/cases/{scenario['case']}/profile").status_code == 404


@pytest.mark.parametrize("operation", ["certification", "status"])
def test_counselor_revocation_removes_existing_case_access_and_records_reason(
    db, client, scenario, operation
):
    with db.transaction() as session:
        session.add(CaseGrant(case_id=scenario["case"], counselor_id=scenario["certified"]))
    with TestClient(client.app, base_url="https://testserver") as counselor_client:
        login(counselor_client, "certified")
        case_path = f"/api/v1/cases/{scenario['case']}/profile"
        assert counselor_client.get(case_path).status_code == 200
        headers = login(client)
        reason = "Reviewed counselor eligibility and ended the current support assignment"
        if operation == "certification":
            path = f"/api/v1/admin/counselor-certifications/{scenario['certified']}"
            body = {"decision": "revoked", "reason": reason}
            action = "identity.certification_revoked"
        else:
            path = f"/api/v1/admin/users/{scenario['certified']}/status"
            body = {"active": False, "reason": reason}
            action = "identity.account_suspended"
        result = client.put(path, headers=versioned(headers), json=body)
        assert result.status_code == 200, result.text
        assert counselor_client.get(case_path).status_code == 401
        with db.transaction() as session:
            grant = session.get(CaseGrant, (scenario["case"], scenario["certified"]))
            assert grant is not None and grant.revoked_at is not None
            assert session.get(Case, scenario["case"]).version == 2
            if operation == "certification":
                assert session.get(UserRole, (scenario["certified"], "counselor")) is None
        events = client.get("/api/v1/admin/audit").json()
        event = next(row for row in events if row["action"] == action)
        assert event["actor_id"] == str(scenario["admin"])
        assert event["target_id"] == str(scenario["certified"])
        assert event["reason"] == reason
        assert event["trace_id"] == result.headers["x-request-id"]


def test_review_rejects_blank_reason_invalid_transition_and_privilege_fields(client, scenario):
    submitted = submit_application(client)
    headers = login(client)
    path = f"/api/v1/admin/counselor-certifications/{scenario['learner']}"
    current = {**headers, "If-Match": submitted.headers["etag"]}
    assert (
        client.put(path, headers=current, json={"decision": "approved", "reason": "  "}).status_code
        == 422
    )
    assert (
        client.put(
            path,
            headers=current,
            json={"decision": "approved", "reason": "Checked", "can_manage_users": True},
        ).status_code
        == 422
    )
    assert (
        client.put(
            path, headers=current, json={"decision": "revoked", "reason": "Checked"}
        ).status_code
        == 409
    )
    assert (
        client.put(
            path,
            headers={**headers, "If-Match": "2"},
            json={"decision": "approved", "reason": "Checked"},
        ).status_code
        == 400
    )
    queue = client.get("/api/v1/admin/counselor-certifications?state=pending").json()
    assert queue["total"] == 1
    assert queue["items"][0]["version"] == submitted.json()["version"]
    assert client.get("/api/v1/admin/audit").json()[0]["action"] == (
        "identity.certification_submitted"
    )


def test_administrator_rechecks_actor_generation_after_capability_change(db, scenario):
    stale_actor = Actor(scenario["admin"], frozenset({"learner"}), credential_version=1)
    with db.transaction() as session:
        # Cache the old User in the same transaction that will authorize the write.
        cached = session.get(User, scenario["admin"])
        assert cached.credential_version == 1
        assert is_administrator(session, stale_actor)
        with db.transaction() as other:
            user = other.get(User, scenario["admin"])
            user.credential_version += 1
            grant = other.get(AdministratorGrant, scenario["admin"])
            grant.granted_at = utcnow()
        # A still-active grant cannot revive an Actor captured before a generation change.
        with pytest.raises(AppError) as error:
            require_administrator(session, stale_actor)
        assert error.value.status == 403
        assert cached.credential_version == 2
        fresh_actor = Actor(scenario["admin"], frozenset({"learner"}), credential_version=2)
        require_administrator(session, fresh_actor)
        with pytest.raises(AppError) as error:
            require_administrator(session, Actor(scenario["admin"], frozenset({"learner"})))
        assert error.value.status == 403


def test_revoked_legacy_counselor_keeps_baseline_access_and_can_resubmit(db, client, scenario):
    with db.transaction() as session:
        assert session.get(UserRole, (scenario["certified"], "learner")) is None
        assert session.get(UserRole, (scenario["certified"], "counselor")) is not None
    with TestClient(client.app, base_url="https://testserver") as legacy_client:
        login(legacy_client, "certified")
        headers = login(client)
        result = client.put(
            f"/api/v1/admin/counselor-certifications/{scenario['certified']}",
            headers=versioned(headers),
            json={"decision": "revoked", "reason": "Updated qualifications required"},
        )
        assert result.status_code == 200, result.text
        assert result.json()["state"] == "revoked"
        assert legacy_client.get("/api/v1/me").status_code == 401
        with db.transaction() as session:
            assert session.get(UserRole, (scenario["certified"], "learner")) is not None
            assert session.get(UserRole, (scenario["certified"], "counselor")) is None
        fresh_headers = login(legacy_client, "certified")
        assert legacy_client.get("/api/v1/me").json()["roles"] == ["learner"]
        assert legacy_client.get("/api/v1/me/administration").json() == {"can_manage_users": False}
        submitted = legacy_client.put(
            "/api/v1/me/counselor-certification",
            headers={**fresh_headers, "If-Match": result.headers["etag"]},
            json={"statement": "Completed additional training and renewed qualifications."},
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["state"] == "pending"
        assert submitted.json()["version"] == result.json()["version"] + 1
        assert legacy_client.get("/api/v1/me").json()["roles"] == ["learner"]


def test_unassigning_missing_counselor_does_not_change_case_or_audit(client, scenario):
    headers = login(client)
    before_cases = client.get("/api/v1/admin/cases").json()
    before_audit = client.get("/api/v1/admin/audit").json()
    case = next(row for row in before_cases["items"] if row["id"] == str(scenario["case"]))
    result = client.put(
        f"/api/v1/admin/cases/{scenario['case']}/counselors/{uuid4()}",
        headers=versioned(headers, case["version"]),
        json={"assigned": False, "reason": "Remove nonexistent counselor assignment"},
    )
    assert result.status_code == 404, result.text
    assert client.get("/api/v1/admin/cases").json() == before_cases
    assert client.get("/api/v1/admin/audit").json() == before_audit


def test_application_submission_rechecks_locked_account_generation(db, scenario):
    from app.core.errors import AppError
    from app.core.types import Actor
    from app.modules.identity import management

    stale = Actor(scenario["learner"], frozenset({"learner"}), 1)
    with db.transaction() as session:
        user = session.get(User, scenario["learner"])
        user.credential_version = 2
    with pytest.raises(AppError) as error, db.transaction() as session:
        management.submit(session, stale, "Training completed", '"1"', "stale-submit")
    assert error.value.status == 401
    with db.transaction() as session:
        assert session.get(CounselorCertification, scenario["learner"]) is None
        user = session.get(User, scenario["learner"])
        user.active = False
    fresh = Actor(scenario["learner"], frozenset({"learner"}), 2)
    with pytest.raises(AppError) as error, db.transaction() as session:
        management.submit(session, fresh, "Training completed", '"1"', "inactive-submit")
    assert error.value.status == 401
