"""End-to-end smoke test.

Exercises the whole product through the HTTP API: register, create a
link, follow the short URL and confirm the click was recorded.

    python scripts/smoke_test.py

Exits non-zero if anything is broken, which makes it usable as a
post-deployment check.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("JWT_SECRET_KEY", "smoke-test-secret-key-never-used-in-production")
os.environ.setdefault("SECRET_KEY", "smoke-test-secret-key-never-used-in-production")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("BASE_URL", "http://localhost:8000")

from fastapi.testclient import TestClient  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}{(' - ' + detail) if detail else ''}")
    if not condition:
        FAILURES.append(label)


def main() -> int:
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        print("LinkHub smoke test")
        print("-" * 40)

        health = client.get("/health")
        check("health endpoint is healthy", health.status_code == 200, health.text)

        email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
        username = f"smoke{uuid.uuid4().hex[:8]}"

        registered = client.post(
            "/api/auth/register",
            json={"email": email, "username": username, "password": "sup3r-secret-pw"},
        )
        check(
            "registration succeeds",
            registered.status_code == 201,
            registered.text[:120],
        )
        if registered.status_code != 201:
            return 1

        token = registered.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        unauthenticated = client.post("/api/links", json={"url": "https://example.com"})
        check(
            "unauthenticated create is rejected with 401",
            unauthenticated.status_code == 401,
            f"got {unauthenticated.status_code}",
        )

        created = client.post(
            "/api/links",
            json={"url": "https://github.com/Aditya-k63/LinkHub", "title": "smoke"},
            headers=headers,
        )
        check("link creation succeeds", created.status_code == 201, created.text[:120])
        if created.status_code != 201:
            return 1

        link = created.json()
        short_code = link["short_code"]

        redirect = client.get(f"/{short_code}", follow_redirects=False)
        check(
            "short URL returns a 307 redirect",
            redirect.status_code == 307,
            f"got {redirect.status_code}",
        )
        check(
            "redirect points at the original URL",
            redirect.headers.get("location") == "https://github.com/Aditya-k63/LinkHub",
            redirect.headers.get("location", "no location header"),
        )

        listing = client.get("/api/links", headers=headers).json()
        counted = next((item for item in listing["links"] if item["id"] == link["id"]), None)
        check(
            "the click was recorded",
            counted is not None and counted["click_count"] >= 1,
            f"click_count={counted['click_count'] if counted else 'n/a'}",
        )

        analytics = client.get(f"/api/analytics/{link['id']}", headers=headers)
        check(
            "analytics reports the click",
            analytics.status_code == 200 and analytics.json()["total_clicks"] >= 1,
            analytics.text[:120],
        )

        qr = client.get(f"/api/qr/{short_code}.png")
        check(
            "QR endpoint serves a PNG",
            qr.status_code == 200 and qr.content.startswith(b"\x89PNG"),
            f"status={qr.status_code}",
        )

        deleted = client.delete(f"/api/links/{link['id']}", headers=headers)
        check("link deletion succeeds", deleted.status_code == 200, deleted.text[:80])

    print("-" * 40)
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
