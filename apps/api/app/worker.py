import logging
import signal
import threading
from collections.abc import Callable, Mapping

from app.core.config import Settings
from app.core.types import JsonObject
from app.infrastructure.db import Database
from app.infrastructure.jobs import claim, finish, renew

logger = logging.getLogger("job_lens.worker")
type Handler = Callable[[JsonObject], None]


def system_ping(payload: JsonObject) -> None:
    if payload:
        raise ValueError("system.ping takes an empty payload")


HANDLERS: dict[str, Handler] = {"system.ping": system_ping}


class Worker:
    def __init__(
        self, database: Database, handlers: Mapping[str, Handler], lease_seconds: int = 60
    ) -> None:
        self.database, self.handlers, self.lease_seconds = database, handlers, lease_seconds

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
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = Settings()
    database = Database.from_settings(config)
    # Handlers are added here with the corresponding feature, never from a payload import path.
    worker = Worker(database, handlers=HANDLERS, lease_seconds=config.job_lease_seconds)
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
