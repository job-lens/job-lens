import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from app.bootstrap import metadata
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import new_token, token_digest
from app.core.types import Actor
from app.infrastructure.db import Database, utcnow
from app.infrastructure.idempotency import (
    CommandResult,
    Scope,
    execute_once,
    fingerprint,
    purge_expired,
)
from app.infrastructure.jobs import claim, enqueue, finish, renew
from app.infrastructure.models import IdempotencyRecord, Job, Notification, NotificationCounter
from app.infrastructure.notifications import append_notifications, mark_read, read_notifications
from app.modules.cases.models import Case, CaseGrant
from app.modules.cases.queries import read_access, scope_predicate
from app.modules.identity.models import Preferences, Profile, SessionRecord, User, UserRole
from app.modules.identity.queries import load_user, resolve_actor
from app.modules.sop.models import SopPlan, SopRevision, SopStep
from app.modules.training.models import StepProgress, Submission, TrainingTask
from app.worker import PERIODIC, Worker, build_handlers, schedule
from pydantic import SecretStr
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def database():
    url = os.getenv("JOB_LENS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("JOB_LENS_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    assert make_url(url).database.endswith("_test"), (
        "refusing destructive tests against a non-test DB"
    )
    os.environ["JOB_LENS_DATABASE_URL"] = url
    config = Config("apps/api/alembic.ini")
    command.upgrade(config, "head")
    db = Database.from_settings(Settings(database_url=SecretStr(url), environment="test"))
    yield db
    db.close()


@pytest.fixture
def db(database):
    with database.engine.begin() as connection:
        connection.execute(text("TRUNCATE " + ",".join(metadata.tables) + " CASCADE"))
    return database


def actors(db):
    with db.transaction() as s:
        learner = User(login_name="learner", password_hash="test-only")
        counselor = User(login_name="counselor", password_hash="test-only")
        s.add_all([learner, counselor])
        s.flush()
        case = Case(learner_id=learner.id)
        s.add(case)
        s.flush()
        s.add(CaseGrant(case_id=case.id, counselor_id=counselor.id))
        return learner.id, counselor.id, case.id


def task(db):
    learner, counselor, case_id = actors(db)
    with db.transaction() as s:
        plan = SopPlan(case_id=case_id, title="文档核验", author_id=counselor)
        s.add(plan)
        s.flush()
        revision = SopRevision(plan_id=plan.id, case_id=case_id, number=1, goal="核验标题")
        s.add(revision)
        s.flush()
        step = SopStep(revision_id=revision.id, id=uuid4(), position=1, instruction="核对标题")
        s.add(step)
        s.flush()
        revision.state = "published"
        revision.published_at = utcnow()
        t = TrainingTask(case_id=case_id, revision_id=revision.id)
        s.add(t)
        s.flush()
        return learner, counselor, case_id, t.id, revision.id, step.id


def test_migration_matches_metadata_and_is_ready(db):
    assert db.ready()
    with db.engine.connect() as c:
        differences = compare_metadata(MigrationContext.configure(c), metadata)
        assert not differences, differences


def test_transaction_rolls_back(db):
    with pytest.raises(RuntimeError), db.transaction() as s:
        s.add(User(login_name="rollback", password_hash="test"))
        s.flush()
        raise RuntimeError("abort")
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(User)) == 0


def test_resource_authorization_revocation_and_list_scope(db):
    learner, counselor, case_id = actors(db)
    actor = Actor(counselor, frozenset({"counselor"}))
    with db.transaction() as s:
        read_access(s, actor, case_id)
        assert s.scalars(select(Case).where(scope_predicate(actor))).all()
        s.execute(update(CaseGrant).values(revoked_at=utcnow()))
    with db.transaction() as s:
        with pytest.raises(AppError) as error:
            read_access(s, actor, case_id)
        assert error.value.status == 404
        assert not s.scalars(select(Case).where(scope_predicate(actor))).all()
        read_access(s, Actor(learner, frozenset({"learner"})), case_id)


def test_preference_constraint_rejects_invalid_volume(db):
    learner, _, _ = actors(db)
    with pytest.raises(IntegrityError), db.transaction() as s:
        s.add(Preferences(user_id=learner, volume=2))
        s.flush()


def test_sop_immutability_and_step_context(db):
    _, _, _, task_id, revision_id, step_id = task(db)
    with pytest.raises(IntegrityError), db.transaction() as s:
        s.execute(
            update(SopRevision).where(SopRevision.id == revision_id).values(goal="overwritten")
        )
    with pytest.raises(IntegrityError), db.transaction() as s:
        s.add(SopStep(revision_id=revision_id, id=uuid4(), position=2, instruction="late insert"))
        s.flush()
    with pytest.raises(IntegrityError), db.transaction() as s:
        s.add(StepProgress(task_id=task_id, revision_id=revision_id, step_id=uuid4()))
        s.flush()
    with db.transaction() as s:
        s.add(StepProgress(task_id=task_id, revision_id=revision_id, step_id=step_id))
        s.flush()


def test_task_uniqueness_and_immutable_submission(db):
    _, _, case_id, task_id, revision_id, _ = task(db)
    with pytest.raises(IntegrityError), db.transaction() as s:
        s.add(TrainingTask(case_id=case_id, revision_id=revision_id))
        s.flush()
    with db.transaction() as s:
        submission = Submission(task_id=task_id, attempt_no=1, snapshot={"steps": []})
        s.add(submission)
        s.flush()
        submission_id = submission.id
    with pytest.raises(IntegrityError), db.transaction() as s:
        s.execute(
            update(Submission)
            .where(Submission.id == submission_id)
            .values(snapshot={"changed": True})
        )


def test_idempotency_concurrent_replay_and_reauthorization(db):
    learner, _, _ = actors(db)
    scope = Scope(learner, "POST", "/test", "same-command-key-0001")
    calls = []

    def invoke():
        with db.transaction() as s:

            def action():
                calls.append(1)
                return CommandResult(
                    201, {"id": "result"}, {"ETag": '"1"', "Set-Cookie": "never-store"}
                )

            return execute_once(s, scope, fingerprint({"x": 1}), lambda: None, action)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: invoke(), range(4)))
    assert len(calls) == 1 and len({str(r.body) for r in results}) == 1
    assert results[0].headers == {"ETag": '"1"'}
    with db.transaction() as s, pytest.raises(AppError):
        execute_once(s, scope, fingerprint({"x": 2}), lambda: None, lambda: None)

    def denied():
        raise AppError(404, "NOT_FOUND", "not found")

    with db.transaction() as s, pytest.raises(AppError):
        execute_once(s, scope, fingerprint({"x": 1}), denied, lambda: None)
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1


def test_notification_order_pagination_isolation_and_rollback(db):
    learner, counselor, resource = actors(db)

    def notify(_):
        with db.transaction() as s:
            append_notifications(s, {counselor, learner}, "test.created", "case", resource)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(notify, range(8)))
    with pytest.raises(RuntimeError), db.transaction() as s:
        append_notifications(s, {learner}, "rolled.back", "case", resource)
        raise RuntimeError("abort")
    with db.transaction() as s:
        page = read_notifications(s, learner, limit=3)
        assert [r.seq for r in page.items] == [1, 2, 3]
        assert page.next_seq == "3" and page.has_more
        end = read_notifications(s, learner, after=8)
        assert not end.items and end.next_seq == "8"
        with pytest.raises(AppError):
            mark_read(s, counselor, page.items[0].id)
        assert s.get(NotificationCounter, learner).seq == 8
        s.get(NotificationCounter, learner).retained_after = 4
        s.execute(
            Notification.__table__.delete().where(
                Notification.recipient_id == learner, Notification.seq <= 4
            )
        )
    with db.transaction() as s:
        with pytest.raises(AppError) as e:
            read_notifications(s, learner, after=2)
        assert e.value.status == 410
        assert read_notifications(s, learner).items[0].seq == 5


def test_job_reclaim_fences_stale_worker_and_exhausts_retry(db):
    with db.transaction() as s:
        jid = enqueue(s, "test", {"x": 1}, "same-job")
        assert enqueue(s, "test", {"x": 1}, "same-job") == jid
    with db.transaction() as s:
        first = claim(s, 10)
    assert first is not None
    with db.transaction() as s:
        assert claim(s, 10) is None
        s.execute(
            update(Job).where(Job.id == jid).values(lease_until=utcnow() - timedelta(seconds=1))
        )
    with db.transaction() as s:
        second = claim(s, 10)
    assert second and second.token != first.token
    with db.transaction() as s:
        assert not finish(s, first)
        assert renew(s, second)
        assert finish(s, second, "UNKNOWN_HANDLER")
    with db.transaction() as s:
        assert s.get(Job, jid).state == "failed"
        assert claim(s) is None


def test_job_skip_locked(db):
    with db.transaction() as s:
        for n in range(2):
            enqueue(s, "test", {}, f"job-{n}")
    locked = Event()
    release = Event()

    def hold():
        with db.transaction() as s:
            first = claim(s)
            locked.set()
            assert release.wait(5)
            return first.job_id

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(hold)
        assert locked.wait(5)
        try:
            with db.transaction() as s:
                second = claim(s)
            assert second is not None
        finally:
            release.set()
        assert future.result() != second.job_id


def test_task_rejects_draft_revision_and_identity_reassignment(db):
    _, counselor, case_id = actors(db)
    with db.transaction() as session:
        plan = SopPlan(case_id=case_id, title="test", author_id=counselor)
        session.add(plan)
        session.flush()
        draft = SopRevision(plan_id=plan.id, case_id=case_id, number=1)
        session.add(draft)
        session.flush()
        rid = draft.id
    with pytest.raises(IntegrityError), db.transaction() as session:
        session.add(TrainingTask(case_id=case_id, revision_id=rid))
        session.flush()
    with db.transaction() as session:
        draft = session.get(SopRevision, rid)
        draft.state, draft.published_at = "published", utcnow()
        session.flush()
        current = TrainingTask(case_id=case_id, revision_id=rid)
        session.add(current)
        session.flush()
        tid = current.id
    with pytest.raises(IntegrityError), db.transaction() as session:
        session.execute(
            update(TrainingTask).where(TrainingTask.id == tid).values(revision_id=uuid4())
        )


def test_task_hint_override_requires_reason(db):
    *_, tid, _, _ = task(db)
    for level, reason in [(0, "text"), (2, None), (2, " "), (None, "text")]:
        with pytest.raises(IntegrityError), db.transaction() as session:
            session.execute(
                update(TrainingTask)
                .where(TrainingTask.id == tid)
                .values(prompt_override=level, prompt_reason=reason)
            )
    with db.transaction() as session:
        session.execute(
            update(TrainingTask)
            .where(TrainingTask.id == tid)
            .values(prompt_override=2, prompt_reason="增加文字提示")
        )


def test_job_success_clears_previous_retry_error(db):
    with db.transaction() as session:
        jid = enqueue(session, "system.ping", {}, "retry-success")
    with db.transaction() as session:
        lease = claim(session)
        assert finish(session, lease, "TRANSIENT")
        session.execute(
            update(Job).where(Job.id == jid).values(next_run_at=utcnow() - timedelta(seconds=1))
        )
    with db.transaction() as session:
        lease = claim(session)
        assert finish(session, lease)
        row = session.get(Job, jid)
        assert row.state == "done" and row.error_code is None


def test_empty_database_migration_roundtrip(db):
    # The fixture above only admits an explicitly named disposable *_test database.
    config = Config("apps/api/alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    assert db.ready()


def signed_in(db, roles=("learner",), *, revoked=False, age=timedelta(), idle=timedelta()):
    """Create a user with roles, a profile and one session; return its raw token."""
    token = new_token()
    now = utcnow()
    with db.transaction() as s:
        user = User(login_name=f"user-{uuid4().hex[:8]}", password_hash="test-only")
        s.add(user)
        s.flush()
        s.add(Profile(user_id=user.id, display_name="测试用户"))
        s.add_all([UserRole(user_id=user.id, role=role) for role in roles])
        s.add(
            SessionRecord(
                user_id=user.id,
                created_at=now - age,
                token_hash=token_digest(token),
                csrf_hash="c" * 64,
                last_seen_at=now - idle,
                expires_at=now + timedelta(hours=12) - age,
                revoked_at=now if revoked else None,
            )
        )
        return user.id, token


def test_session_resolves_to_an_actor_with_declared_roles(db):
    user_id, token = signed_in(db, ("learner", "counselor"))
    with db.transaction() as s:
        actor = resolve_actor(s, token, utcnow())
        assert actor.user_id == user_id
        assert actor.roles == frozenset({"learner", "counselor"})
        view = load_user(s, actor)
        assert view.display_name == "测试用户"
        assert view.roles == ("counselor", "learner")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"revoked": True},
        {"age": timedelta(hours=13)},
        {"idle": timedelta(hours=3)},
        {"roles": ()},
    ],
)
def test_session_resolution_rejects_unusable_sessions(db, kwargs):
    _, token = signed_in(db, **kwargs)
    with db.transaction() as s, pytest.raises(AppError) as error:
        resolve_actor(s, token, utcnow())
    assert error.value.status == 401


def test_session_resolution_rejects_an_unknown_token(db):
    signed_in(db)
    with db.transaction() as s, pytest.raises(AppError) as error:
        resolve_actor(s, new_token(), utcnow())
    assert error.value.status == 401


def test_user_without_a_profile_is_not_readable(db):
    with db.transaction() as s:
        user = User(login_name="no-profile", password_hash="test-only")
        s.add(user)
        s.flush()
        actor = Actor(user.id, frozenset({"learner"}))
    with db.transaction() as s, pytest.raises(AppError) as error:
        load_user(s, actor)
    assert error.value.status == 404
def test_expired_idempotency_records_are_purged(db):
    learner, _, _ = actors(db)
    with db.transaction() as s:
        for name, age in [("stale", timedelta(hours=1)), ("live", -timedelta(hours=1))]:
            s.add(
                IdempotencyRecord(
                    actor_id=learner,
                    method="POST",
                    path=f"/{name}",
                    key=f"{name}-key-000000000001",
                    fingerprint="f" * 64,
                    response_headers={},
                    expires_at=utcnow() - age,
                )
            )
    with db.transaction() as s:
        assert purge_expired(s, utcnow()) == 1
    with db.transaction() as s:
        assert [r.path for r in s.scalars(select(IdempotencyRecord))] == ["/live"]


def test_periodic_job_enters_once_per_slot(db):
    now = utcnow()
    with db.transaction() as s:
        first = schedule(s, "system.ping", 3600, now)
        assert schedule(s, "system.ping", 3600, now + timedelta(minutes=5)) == first
        later = schedule(s, "system.ping", 3600, now + timedelta(hours=1))
    assert later != first
    with db.transaction() as s:
        rows = s.scalars(select(Job).order_by(Job.next_run_at)).all()
        assert len(rows) == 2
        assert rows[1].next_run_at > rows[0].next_run_at


def test_worker_rearms_a_periodic_job_after_finishing(db):
    with db.transaction() as s:
        schedule(s, "system.ping", 3600, utcnow())
    worker = Worker(db, build_handlers(db), periodic=PERIODIC | {"system.ping": 3600})
    assert worker.run_once()
    with db.transaction() as s:
        states = sorted(r.state for r in s.scalars(select(Job)))
        assert states == ["done", "pending"], states
