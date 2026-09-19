import logging
import signal
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.types import JsonObject
from app.infrastructure.db import Database, utcnow
from app.infrastructure.idempotency import purge_expired
from app.infrastructure.jobs import claim, enqueue, finish, renew

logger = logging.getLogger("job_lens.worker")
type Handler = Callable[[JsonObject], None]

# Sweeps that must run whether or not anyone is using the system. Seconds between runs.
PERIODIC: dict[str, int] = {"system.purge_idempotency": 3600}


def system_ping(payload: JsonObject) -> None:
    if payload:
        raise ValueError("system.ping takes an empty payload")


def build_handlers(database: Database) -> dict[str, Handler]:
    """Sweeps need their own transaction, so they close over the database rather than take one."""

    def purge_idempotency(payload: JsonObject) -> None:
        with database.transaction() as session:
            purge_expired(session, utcnow())

    return {"system.ping": system_ping, "system.purge_idempotency": purge_idempotency}


def slot_start(now: datetime, period: int) -> datetime:
    return datetime.fromtimestamp(int(now.timestamp()) // period * period, UTC)


def schedule(session: Session, kind: str, period: int, now: datetime) -> UUID:
    """Seed or re-arm a periodic job. The slot is in the dedupe key so the next run can enter."""
    start = slot_start(now, period)
    return enqueue(session, kind, {}, f"{kind}:{start.isoformat()}", run_at=start)


class Worker:
    def __init__(
        self,
        database: Database,
        handlers: Mapping[str, Handler],
        lease_seconds: int = 60,
        periodic: Mapping[str, int] | None = None,
    ) -> None:
        self.database, self.handlers, self.lease_seconds = database, handlers, lease_seconds
        self.periodic = periodic or {}

    def run_once(self) -> bool:
        with self.database.transaction() as session:
            lease = claim(session, self.lease_seconds)
        if lease is None:
            return False
        stop = threading.Event()

        def heartbeat() -> None:
            while not stop.wait(lease.seconds / 3):
                try:
                    with self.database.transaction() as session:
                        if not renew(session, lease):
                            return
                except Exception:
                    logger.warning("lease_renewal_failed job_id=%s", lease.job_id)
                    return

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        error: str | None = None
        try:
            handler = self.handlers.get(lease.kind)
            if handler is None:
                error = "UNKNOWN_HANDLER"
            else:
                handler(lease.payload)
        except Exception as exc:
            error = type(exc).__name__
        finally:
            stop.set()
            thread.join(timeout=10)
        with self.database.transaction() as session:
            if not finish(session, lease, error):
                logger.warning("lease_lost job_id=%s", lease.job_id)
            elif lease.kind in self.periodic:
                # Re-arm in the same transaction that closed this run, or a crash loses the cadence.
                period = self.periodic[lease.kind]
                schedule(session, lease.kind, period, utcnow() + timedelta(seconds=period))
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = Settings()
    database = Database.from_settings(config)
    # Handlers are added here with the corresponding feature, never from a payload import path.
    handlers = build_handlers(database)
    worker = Worker(
        database, handlers=handlers, lease_seconds=config.job_lease_seconds, periodic=PERIODIC
    )
    with database.transaction() as session:
        for kind, period in PERIODIC.items():
            schedule(session, kind, period, utcnow())
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        while not stop.is_set():
            try:
                worked = worker.run_once()
            except Exception as exc:
                logger.error("worker_iteration_failed type=%s", type(exc).__name__)
                worked = False
            if not worked:
                stop.wait(config.job_poll_seconds)
    finally:
        database.close()


if __name__ == "__main__":
    main()
