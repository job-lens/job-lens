from alembic import context
from app.bootstrap import metadata
from app.core.config import Settings
from app.infrastructure.db import Database

config = context.config
settings = Settings()


def offline() -> None:
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def online() -> None:
    db = Database.from_settings(settings)
    try:
        with db.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        db.close()


if context.is_offline_mode():
    offline()
else:
    online()
