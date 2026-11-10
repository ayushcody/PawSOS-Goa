"""Alembic entry point: connect to the database and run pending migrations."""

from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.config import get_settings
from app.db import Base

target_metadata = Base.metadata


def run_migrations() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
