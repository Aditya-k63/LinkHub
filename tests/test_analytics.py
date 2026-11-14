"""Analytics, admin, health and rate limit tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

TARGET_URL = "https://github.com/Aditya-k63/LinkHub"


def test_analytics_requires_authentication(client: TestClient):
    assert client.get("/api/analytics/some-id").status_code == 401


def test_analytics_reports_the_clicks(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    client.get(f"/{created['short_code']}", follow_redirects=False)
    client.get(f"/{created['short_code']}", follow_redirects=False)

    response = client.get(f"/api/analytics/{created['id']}", headers=auth_headers)
    assert response.status_code == 200

    body = response.json()
    assert body["total_clicks"] == 2
    assert body["link"]["short_code"] == created["short_code"]
    assert isinstance(body["daily_clicks"], list)


def test_analytics_parses_the_user_agent(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    client.get(
        f"/{created['short_code']}",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"},
        follow_redirects=False,
    )

    body = client.get(f"/api/analytics/{created['id']}", headers=auth_headers).json()
    browsers = [entry["browser"] for entry in body["top_browsers"]]
    assert any("Chrome" in name for name in browsers)


def test_bot_clicks_are_flagged(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    client.get(
        f"/{created['short_code']}",
        headers={"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"},
        follow_redirects=False,
    )

    body = client.get(f"/api/analytics/{created['id']}", headers=auth_headers).json()
    # Bot clicks are recorded but excluded from the human-facing totals.
    assert body["all_time_clicks"] == 1
    assert body["total_clicks"] == 0


def test_admin_stats_requires_an_admin(client: TestClient, auth_headers: dict):
    response = client.get("/api/admin/stats", headers=auth_headers)
    assert response.status_code == 403


def test_admin_stats_is_available_to_admins(client: TestClient, admin_headers: dict):
    response = client.get("/api/admin/stats", headers=admin_headers)
    assert response.status_code == 200

    body = response.json()
    assert body["total_links"] >= 0
    assert body["total_clicks"] >= 0


def test_health_check_reports_healthy(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"] == "ok"


def test_health_check_sets_a_request_id(client: TestClient):
    response = client.get("/health")
    assert response.headers.get("x-request-id")


def test_rate_limit_returns_429(client: TestClient, auth_headers: dict, monkeypatch):
    import uuid

    from app.core import config

    monkeypatch.setattr(config.settings, "RATE_LIMIT_PER_MINUTE", 3)
    assert config.settings.RATE_LIMIT_PER_MINUTE == 3

    # A dedicated client identity keeps this test's bucket separate.
    client_id = f"10.0.0.{uuid.uuid4().int % 250 + 1}"
    headers = {"X-Forwarded-For": client_id}

    # Writes get the tighter budget; reads are allowed 5x as many.
    statuses = [
        client.post("/api/links", json={"url": TARGET_URL}, headers=headers).status_code
        for _ in range(6)
    ]
    assert 429 in statuses
    assert client.post("/api/links", json={"url": TARGET_URL}, headers=headers).status_code == 429


def test_openapi_schema_is_valid(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    assert schema["info"]["title"] == "LinkHub"
    assert "/{short_code}" in schema["paths"]
