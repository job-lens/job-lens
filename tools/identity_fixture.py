"""Disposable browser accounts; refuses ordinary and production databases."""

import os
import sys
from datetime import timedelta

from app.core.config import Settings
from app.core.security import hash_password
from app.infrastructure.db import Database, utcnow
from app.modules.identity.models import Preferences, Profile, SessionRecord, User, UserRole
from sqlalchemy import select, update
from sqlalchemy.engine import make_url


def main() -> None:
    settings = Settings()
    name = make_url(settings.database_url.get_secret_value()).database or ""
    if settings.environment != "test" or not name.endswith("_test"):
        raise SystemExit("Browser fixtures require environment=test and a *_test database")
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    if command not in {"seed", "expire"}:
        raise SystemExit("Usage: identity_fixture.py seed|expire")
    database = Database.from_settings(settings)
    try:
        with database.transaction() as session:
            if command == "seed":
                password = os.environ["E2E_PASSWORD"]
                for role in ("learner", "counselor"):
                    login = "fixture_" + role
                    if session.scalar(select(User.id).where(User.login_name == login)):
                        raise SystemExit("Fixture already exists; refusing to overwrite an account")
                    user = User(login_name=login, password_hash=hash_password(password))
                    session.add(user)
                    session.flush()
                    session.add_all(
                        [
                            UserRole(user_id=user.id, role=role),
                            Profile(user_id=user.id, display_name="浏览器测试" + role),
                            Preferences(user_id=user.id),
                        ]
                    )
            else:
                user_id = session.scalar(
                    select(User.id).where(User.login_name == "fixture_learner")
                )
                if user_id is None:
                    raise SystemExit("Missing disposable fixture account")
                session.execute(
                    update(SessionRecord)
                    .where(SessionRecord.user_id == user_id)
                    .values(last_seen_at=utcnow() - timedelta(hours=3))
                )
        print("PASS: disposable identity fixture " + command)
    finally:
        database.close()


if __name__ == "__main__":
    main()
