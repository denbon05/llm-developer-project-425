"""Alembic migration environment for the ticketing schema."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from ticketing.config import get_settings
from ticketing.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Same shared registry as app startup (Base.metadata.create_all): Alembic
# compares/migrates every table registered on Base (Ticket, Message, …).
target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    # SQL script mode: no live DB connection; URL + metadata only.
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Live connection mode: apply migrations against the real database.
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    # emit SQL, do not connect
    run_migrations_offline()
else:
    run_migrations_online()
