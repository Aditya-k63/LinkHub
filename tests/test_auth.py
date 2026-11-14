"""Authentication endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_register_returns_a_token(client: TestClient, unique_email: str, unique_username: str):
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "username": unique_username,
            "password": "sup3r-secret-pw",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["username"] == unique_username


def test_register_rejects_duplicate_email(
    client: TestClient, unique_email: str, unique_username: str
):
    payload = {"email": unique_email, "username": unique_username, "password": "sup3r-secret-pw"}
    assert client.post("/api/auth/register", json=payload).status_code == 201

    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "username": unique_username + "x",
            "password": "sup3r-secret-pw",
        },
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_register_rejects_short_password(
    client: TestClient, unique_email: str, unique_username: str
):
    response = client.post(
        "/api/auth/register",
        json={"email": unique_email, "username": unique_username, "password": "short"},
    )
    assert response.status_code == 422


def test_login_returns_a_token(client: TestClient, unique_email: str, unique_username: str):
    client.post(
        "/api/auth/register",
        json={"email": unique_email, "username": unique_username, "password": "sup3r-secret-pw"},
    )

    response = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "sup3r-secret-pw"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_rejects_wrong_password(client: TestClient, unique_email: str, unique_username: str):
    client.post(
        "/api/auth/register",
        json={"email": unique_email, "username": unique_username, "password": "sup3r-secret-pw"},
    )

    response = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_the_profile(client: TestClient, auth_headers: dict, unique_username: str):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == unique_username


def test_invalid_token_is_rejected(client: TestClient):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
