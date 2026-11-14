"""Shared test fixtures.

The suite never touches a real database or a real Redis instance: the
application is pointed at an in-memory SQLite database and the Redis
client is disabled before ``app`` is imported.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

# These must be set before app.core.config is imported.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["REDIS_URL"] = ""
os.environ["JWT_SECRET_KEY"] = "test-secret-key-never-used-in-production-0123456789"
os.environ["SECRET_KEY"] = "test-secret-key-never-used-in-production-0123456789"
os.environ["ENVIRONMENT"] = "development"
os.environ["BASE_URL"] = "http://testserver"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture()
def unique_username() -> str:
    return f"user{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def auth_token(client: TestClient, unique_email: str, unique_username: str) -> str:
    """Register a user and return their access token."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "username": unique_username,
            "password": "sup3r-secret-pw",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


@pytest.fixture()
def auth_headers(auth_token: str) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture()
def admin_headers(db: Session, unique_email: str, unique_username: str) -> dict:
    """Register a user and promote them to admin."""
    from app.core.security import create_access_token, get_password_hash
    from app.db.models import User

    user = User(
        email=unique_email,
        username=unique_username,
        hashed_password=get_password_hash("sup3r-secret-pw"),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "is_admin": True})
    return {"Authorization": f"Bearer {token}"}
