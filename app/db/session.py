"""Database engine and session management.

The previous implementation wrapped ``create_engine`` in a try/except and
claimed to fall back to SQLite. ``create_engine`` is lazy - it never opens a
connection - so that fallback could never fire and the process happily
started with a database it could not reach. The engine is now probed with a
real connection before the application accepts traffic.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.logger import logger

SQLITE_FALLBACK_URL = "sqlite:///./linkhub.db"

#: SQLite URLs that live in memory and therefore need a single shared
#: connection to stay visible to every session.
IN_MEMORY_SQLITE = {"sqlite://", "sqlite:///:memory:", "sqlite+pysqlite://"}


def _build_engine(database_url: str) -> Engine:
    """Create an engine for ``database_url``."""
    if database_url.startswith("sqlite"):
        connect_args: dict[str, object] = {"check_same_thread": False}

        if database_url in IN_MEMORY_SQLITE:
            # One connection shared by every session, otherwise each
            # session would see its own empty database.
            engine = create_engine(
                database_url,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
            return engine

        # A file-backed database gets a normal pool. Using StaticPool here
        # would make every session share one connection, and two
        # concurrent commits would then fight over the same transaction
        # ("cannot commit - no transaction is active").
        connect_args["timeout"] = 30
        engine = create_engine(database_url, connect_args=connect_args)

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:
            # WAL lets readers and a writer work at the same time;
            # busy_timeout makes a blocked writer wait instead of failing.
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000")
            finally:
                cursor.close()

        return engine

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
