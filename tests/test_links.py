"""Link creation, redirect and lifecycle tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

TARGET_URL = "https://github.com/Aditya-k63/LinkHub"


def test_creating_a_link_requires_authentication(client: TestClient):
    """Unauthenticated writes must return 401, not a 500 from the database."""
    response = client.post("/api/links", json={"url": TARGET_URL})
    assert response.status_code == 401


def test_create_link_returns_the_short_url(client: TestClient, auth_headers: dict):
    response = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers)
    assert response.status_code == 201

    body = response.json()
    assert body["short_url"].endswith(f"/{body['short_code']}")
    assert body["original_url"] == TARGET_URL
    assert body["click_count"] == 0
    assert body["qr_code"].startswith("data:image/png;base64,")


def test_short_link_redirects_with_307(client: TestClient, auth_headers: dict):
    """The short URL must actually redirect - this is the core feature."""
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    response = client.get(f"/{created['short_code']}", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == TARGET_URL


def test_redirect_records_a_click(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    client.get(f"/{created['short_code']}", follow_redirects=False)
    client.get(f"/{created['short_code']}", follow_redirects=False)

    links = client.get("/api/links", headers=auth_headers).json()
    match = next(link for link in links["links"] if link["id"] == created["id"])
    assert match["click_count"] == 2


def test_unknown_code_returns_404(client: TestClient):
    response = client.get("/definitely-not-a-real-code", follow_redirects=False)
    assert response.status_code == 404


def test_json_resolve_endpoint(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    response = client.get(f"/api/links/{created['short_code']}")
    assert response.status_code == 200
    assert response.json()["redirect_url"] == TARGET_URL


def test_expired_link_returns_410(client: TestClient, auth_headers: dict):
    created = client.post(
        "/api/links",
        json={"url": TARGET_URL, "expires_in_hours": 1},
        headers=auth_headers,
    ).json()

    # Move the expiry into the past.
    from datetime import timedelta

    from app.core.identifiers import to_uuid
    from app.db.models import Link, utcnow
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        link = session.get(Link, to_uuid(created["id"]))
        link.expires_at = utcnow() - timedelta(minutes=5)
        session.commit()
    finally:
        session.close()

    response = client.get(f"/{created['short_code']}", follow_redirects=False)
    assert response.status_code == 410


def test_disabled_link_returns_404(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    response = client.put(
        f"/api/links/{created['id']}", json={"is_active": False}, headers=auth_headers
    )
    assert response.status_code == 200

    redirect = client.get(f"/{created['short_code']}", follow_redirects=False)
    assert redirect.status_code == 404


def test_password_protected_link(client: TestClient, auth_headers: dict):
    created = client.post(
        "/api/links",
        json={"url": TARGET_URL, "password": "letmein"},
        headers=auth_headers,
    ).json()

    blocked = client.get(f"/{created['short_code']}", follow_redirects=False)
    assert blocked.status_code == 403

    unlocked = client.get(
        f"/{created['short_code']}", params={"password": "letmein"}, follow_redirects=False
    )
    assert unlocked.status_code == 307
    assert unlocked.headers["location"] == TARGET_URL


def test_custom_alias_is_used(client: TestClient, auth_headers: dict):
    created = client.post(
        "/api/links",
        json={"url": TARGET_URL, "custom_alias": "my-alias"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert created.json()["short_code"] == "my-alias"


def test_reserved_alias_is_rejected(client: TestClient, auth_headers: dict):
    response = client.post(
        "/api/links",
        json={"url": TARGET_URL, "custom_alias": "api"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "reserved" in response.json()["detail"]


def test_invalid_aliases_are_rejected(client: TestClient, auth_headers: dict):
    for alias in ["ab", "has space", "bad!char"]:
        response = client.post(
            "/api/links",
            json={"url": TARGET_URL, "custom_alias": alias},
            headers=auth_headers,
        )
        assert response.status_code == 400, alias


def test_over_long_alias_is_rejected(client: TestClient, auth_headers: dict):
    response = client.post(
        "/api/links",
        json={"url": TARGET_URL, "custom_alias": "way-too-long-alias"},
        headers=auth_headers,
    )
    assert response.status_code in (400, 422)


def test_duplicate_alias_is_rejected(client: TestClient, auth_headers: dict):
    payload = {"url": TARGET_URL, "custom_alias": "taken-code"}
    assert client.post("/api/links", json=payload, headers=auth_headers).status_code == 201

    response = client.post("/api/links", json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert "already taken" in response.json()["detail"]


def test_links_are_scoped_to_their_owner(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    other = client.post(
        "/api/auth/register",
        json={
            "email": "someone-else@example.com",
            "username": "someoneelse",
            "password": "sup3r-secret-pw",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    listing = client.get("/api/links", headers=other_headers).json()
    assert all(link["id"] != created["id"] for link in listing["links"])

    assert client.delete(f"/api/links/{created['id']}", headers=other_headers).status_code == 404


def test_pagination_is_bounded(client: TestClient, auth_headers: dict):
    assert client.get("/api/links?limit=100000", headers=auth_headers).status_code == 422
    assert client.get("/api/links?page=0", headers=auth_headers).status_code == 422


def test_delete_link(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    assert client.delete(f"/api/links/{created['id']}", headers=auth_headers).status_code == 200
    assert client.get(f"/{created['short_code']}", follow_redirects=False).status_code == 404


def test_update_link_changes_the_destination(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    response = client.put(
        f"/api/links/{created['id']}",
        json={"original_url": "https://example.com/updated"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    redirect = client.get(f"/{created['short_code']}", follow_redirects=False)
    assert redirect.headers["location"] == "https://example.com/updated"


def test_malformed_link_id_returns_400(client: TestClient, auth_headers: dict):
    response = client.put(
        "/api/links/not-a-uuid", json={"title": "x"}, headers=auth_headers
    )
    assert response.status_code == 400


def test_qr_endpoint_returns_png(client: TestClient, auth_headers: dict):
    created = client.post("/api/links", json={"url": TARGET_URL}, headers=auth_headers).json()

    response = client.get(f"/api/qr/{created['short_code']}.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
