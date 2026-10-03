"""Operator-only capability provisioning. Dry-run by default; never used by startup/signup."""

import argparse
from uuid import UUID, uuid4

from app.core.config import Settings
from app.infrastructure.db import Database, utcnow
from app.modules.identity.models import AdministratorGrant, ManagementEvent, User
from sqlalchemy import select, text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Explicitly apply instead of dry-run")
    args = parser.parse_args()
    reason = args.reason.strip()
    if not reason or len(reason) > 1000:
        parser.error("reason must contain 1–1000 characters")
    db = Database.from_settings(Settings())
    try:
        with db.transaction() as s:
            # Serialize operator capability changes; never expose this path over HTTP.
            s.execute(text("SELECT pg_advisory_xact_lock(72631841)"))
            user = s.scalar(select(User).where(User.id == args.user_id).with_for_update())
            if user is None or (not args.revoke and not user.active):
                raise SystemExit("Target must be an existing active account for a grant")
            grant = s.get(AdministratorGrant, user.id)
            current = bool(grant and grant.revoked_at is None)
            desired = not args.revoke
            print(f"Account {user.id}: administrator {current} -> {desired}")
            if not args.apply:
                print("Dry run only. No account or permission changed. Review before --apply.")
                return
            if current == desired:
                print("No change required.")
                return
            if desired:
                if grant is None:
                    s.add(AdministratorGrant(user_id=user.id, granted_at=utcnow()))
                else:
                    grant.granted_at, grant.revoked_at = utcnow(), None
            elif grant:
                grant.revoked_at = utcnow()
            user.credential_version += 1

            s.add(
                ManagementEvent(
                    actor_id=None,
                    target_id=user.id,
                    action="identity.operator_admin_revoked"
                    if args.revoke
                    else "identity.operator_admin_granted",
                    reason=reason,
                    trace_id=uuid4().hex,
                )
            )
        print("Applied. Account must sign in again. Retain operator change-control evidence.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
