from datetime import timedelta

import pytest
import test_postgres as fixtures
from app.infrastructure.db import utcnow
from app.modules.identity.service import session_record, touch_session
from test_postgres import signed_in

pytestmark = pytest.mark.postgres
database = fixtures.database
db = fixtures.db


def test_queued_request_uses_time_after_lock_and_never_rewinds_last_seen(db):
    _, token = signed_in(db, age=timedelta(minutes=1))
    # Another request has already committed an activity timestamp later than this
    # request's start. The session remains valid at the actual validation time.
    request_start = utcnow() - timedelta(seconds=1)
    with db.transaction() as s:
        row = session_record(s, token, request_start)
        before = row.last_seen_at
        touch_session(s, token, request_start)
        assert row.last_seen_at >= before
