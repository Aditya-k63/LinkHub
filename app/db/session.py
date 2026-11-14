"""Database engine and session management.

The previous implementation wrapped ``create_engine`` in a try/except and
claimed to fall back to SQLite. ``create_engine`` is lazy - it never opens a
connection - so that fallback could never fire and the process happily
started with a database it could not reach. The engine is now probed with a
real connection before the application accepts traffic.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.logger import logger

SQLITE_FALLBACK_URL = "sqlite:///./linkhub.db"


def _build_engine(database_url: str) -> Engine:
    """Create an engine for ``database_url``."""
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    connect_args = {"sslmode": "require"} if "neon.tech" in database_url else {}
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
        pool_recycle=1800,
        connect_args=connect_args,
    )


def _engine_is_usable(engine: Engine) -> bool:
    """Return True if the engine can actually open a connection."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - depends on the environment
        logger.warning("Database connectivity check failed: %s", exc)
        return False


def _select_engine() -> Engine:
    """Return a working engine, falling back to SQLite only in development."""
    try:
        engine = _build_engine(settings.DATABASE_URL)
    except Exception as exc:  # pragma: no cover - malformed URL
        logger.warning("Could not build engine for DATABASE_URL: %s", exc)
        engine = None  # type: ignore[assignment]

    if engine is not None and _engine_is_usable(engine):
        return engine

    if settings.is_production:
        # A production process must not silently serve from a local SQLite
        # file - fail loudly instead.
        raise RuntimeError(
            "Cannot reach the configured database. Check DATABASE_URL and that "
            "the database is reachable from this host."
        )

    logger.warning("Falling back to a local SQLite database")
    fallback = _build_engine(SQLITE_FALLBACK_URL)
    _engine_is_usable(fallback)
    return fallback


engine = _select_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
