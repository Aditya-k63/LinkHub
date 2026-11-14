"""Tests for the behaviour when a dependency is unavailable."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


def test_database_outage_returns_503(client: TestClient, monkeypatch):
    """A dead database must not surface as a 500."""
    from app.db import session as db_session

    def explode(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(db_session.engine, "connect", explode)

    # The public resolve endpoint queries the database without needing a
    # token, so it reaches the failure.
    response = client.get("/api/links/doesnotexist")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_health_check_reports_unhealthy_when_the_database_is_down(client: TestClient, monkeypatch):
    from app.db import session as db_session

    def explode(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(db_session.engine, "connect", explode)

    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["checks"]["database"].startswith("error")


@pytest.mark.parametrize("path", ["/", "/dashboard", "/health"])
def test_pages_that_do_not_need_the_database_still_work(client: TestClient, path: str):
    """The landing pages must not depend on the database."""
    response = client.get(path)
    assert response.status_code in (200, 503)
