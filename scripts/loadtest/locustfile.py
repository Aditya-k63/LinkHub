"""Locust load test for the redirect path.

Run against a locally running instance:

    # terminal 1
    docker compose up --build

    # terminal 2
    locust -f scripts/loadtest/locustfile.py --host http://localhost:8000

The scenarios mirror real traffic: most requests follow an existing short
link, a smaller share create new links through the authenticated API.

Set SHORT_CODE to the code of an existing link, or leave it empty to have
the script create one on startup.
"""

from __future__ import annotations

import os
import uuid

import requests
from locust import HttpUser, between, events, task

TARGET_URL = "https://github.com/Aditya-k63/LinkHub"
SHORT_CODE = os.getenv("SHORT_CODE", "")

state: dict[str, str] = {"short_code": SHORT_CODE}


@events.test_start.add_listener
def on_test_start(environment, **kwargs):  # pragma: no cover - locust hook
    """Create a link to redirect to, unless one was supplied."""
    if state["short_code"]:
        return

    base = (environment.host or "").rstrip("/")
    email = f"loadtest-{uuid.uuid4().hex[:10]}@example.com"
    username = f"load{uuid.uuid4().hex[:8]}"

    response = requests.post(
        f"{base}/api/auth/register",
        json={"email": email, "username": username, "password": "loadtest-password"},
        timeout=30,
    )
    if response.status_code != 201:
        print(f"Could not register the load-test user: {response.status_code}")
        return

    token = response.json()["access_token"]
    created = requests.post(
        f"{base}/api/links",
        json={"url": TARGET_URL, "title": "load test"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if created.status_code == 201:
        state["short_code"] = created.json()["short_code"]
        print(f"Load test target: /{state['short_code']}")


class RedirectUser(HttpUser):
    """Simulates visitors following short links."""

    wait_time = between(0.1, 0.5)

    @task(9)
    def follow_short_link(self):
        if state["short_code"]:
            self.client.get(
                f"/{state['short_code']}",
                name="/{short_code} (redirect)",
                allow_redirects=False,
            )

    @task(1)
    def hit_homepage(self):
        self.client.get("/", name="/ (homepage)")


class LinkCreatorUser(HttpUser):
    """Simulates authenticated users creating links."""

    wait_time = between(1, 3)

    def on_start(self):
        email = f"creator-{uuid.uuid4().hex[:10]}@example.com"
        username = f"creator{uuid.uuid4().hex[:8]}"
        response = self.client.post(
            "/api/auth/register",
            json={"email": email, "username": username, "password": "loadtest-password"},
        )
        if response.status_code == 201:
            self.token = response.json()["access_token"]
        else:
            self.token = ""

    @task
    def create_link(self):
        if not self.token:
            return
        self.client.post(
            "/api/links",
            json={"url": TARGET_URL},
            headers={"Authorization": f"Bearer {self.token}"},
            name="POST /api/links",
        )
