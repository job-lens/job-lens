"""Enqueue a system ping and require a separately running worker to complete it."""

import time
from uuid import uuid4

from app.core.config import Settings
from app.infrastructure.db import Database
from app.infrastructure.jobs import enqueue
from app.infrastructure.models import Job
from sqlalchemy import select


def main() -> None:
    database = Database.from_settings(Settings())
    try:
        with database.transaction() as session:
            job_id = enqueue(session, "system.ping", {}, "smoke-" + uuid4().hex)
        for _ in range(30):
            with database.transaction() as session:
                state = session.scalar(select(Job.state).where(Job.id == job_id))
            if state == "done":
                print("PASS: durable job processed by the running worker")
                return
            if state == "failed":
                raise SystemExit("Worker job failed")
            time.sleep(1)
        raise SystemExit("Worker did not acknowledge the job within 30 seconds")
    finally:
        database.close()


if __name__ == "__main__":
    main()
