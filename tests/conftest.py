"""Shared test setup.

Tests use their own database (pawsos_test) and their own photo folder, so
they can wipe both without touching your development data. This file runs
before any test module is imported, which is why the environment is set here.
"""

import os
import tempfile

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://pawsos:pawsos@localhost:5440/pawsos_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["MEDIA_DIR"] = tempfile.mkdtemp(prefix="pawsos-test-media-")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import get_engine
from app.main import create_app


@pytest.fixture(scope="session")
def _migrated_db() -> None:
    """Bring the test database up to the latest migration, once per test run."""
    try:
        with get_engine().connect():
            pass
    except OperationalError:
        pytest.fail(
            "Cannot reach the test database. Start it with:  docker compose up -d", pytrace=False
        )
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def db(_migrated_db) -> Session:
    """An empty database for each test."""
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE events, photos, reports, cases RESTART IDENTITY CASCADE")
        )
    with Session(engine) as session:
        yield session


@pytest.fixture
def client() -> TestClient:
    # A fresh app per test, so simulator chats never leak between tests.
    return TestClient(create_app())
