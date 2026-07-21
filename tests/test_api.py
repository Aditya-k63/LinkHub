import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_home_page():
    response = client.get("/")
    assert response.status_code == 200


def test_register():
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpass123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


def test_login():
    token = test_register()
    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_create_link():
    token = test_register()
    response = client.post(
        "/api/links",
        json={"url": "https://github.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "short_code" in data
    assert "short_url" in data
    return data["short_code"]


def test_list_links():
    token = test_register()
    test_create_link()
    response = client.get(
        "/api/links",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "links" in data
    assert data["total"] >= 1


def test_redirect():
    token = test_register()
    short_code = test_create_link()
    response = client.get(f"/api/links/{short_code}")
    assert response.status_code == 200
    data = response.json()
    assert "redirect_url" in data
