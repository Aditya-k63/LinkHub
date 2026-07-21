from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings

try:
    if settings.DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=5,
            connect_args={"sslmode": "require"} if "neon.tech" in settings.DATABASE_URL else {},
        )
except Exception as e:
    import logging
    logging.warning(f"Database connection failed: {e}. Using SQLite fallback.")
    engine = create_engine(
        "sqlite:///./linkhub.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
