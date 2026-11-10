"""Database engine and sessions.

A session is one unit of work: everything inside it is saved together on
commit, or not at all if something fails.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    # Creating an engine does not connect; the first query does.
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def new_session() -> Session:
    """A session for code that runs outside a web request, such as background jobs."""
    return _session_factory()()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: commit if the request succeeds, roll back if it fails."""
    session = new_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
