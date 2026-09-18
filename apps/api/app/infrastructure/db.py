from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, Uuid, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import Settings

SCHEMA_REVISION = "0002_integrity"


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def utcnow() -> datetime:
    return datetime.now(UTC)


class Entity:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Database:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.sessions = sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_settings(cls, settings: Settings) -> "Database":
        return cls(
            create_engine(
                settings.database_url.get_secret_value(),
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_timeout=3,
                connect_args={
                    "connect_timeout": 5,
                    "options": "-c statement_timeout=5000 -c lock_timeout=3000",
                },
            )
        )

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with self.sessions.begin() as session:
            yield session

    def ready(self) -> bool:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return bool(
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == SCHEMA_REVISION
            )

    def close(self) -> None:
        self.engine.dispose()
