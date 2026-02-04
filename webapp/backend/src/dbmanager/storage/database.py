"""
Database setup for the IDS dashboard.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DEFAULT_DB_URL = "sqlite:///./data/ids_dashboard.db"


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def _resolve_db_url() -> str:
    db_url = (Path.cwd() / "data" / "ids_dashboard.db").as_posix()
    return DEFAULT_DB_URL.replace("./data/ids_dashboard.db", db_url)


def _build_engine():
    from os import getenv

    url = getenv("DATABASE_URL", _resolve_db_url())
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create database tables if they do not exist."""
    db_path = Path("data")
    db_path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_session():
    """Yield a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
