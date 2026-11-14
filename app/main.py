"""LinkHub application entrypoint."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import admin, analytics, auth, links, qr
from app.core.config import settings
from app.core.logger import logger
from app.db.session import engine, get_db
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.click_recorder import record_click
from app.services.click_tracker import build_click_event
from app.services.redis_cache import redis_healthy
from app.services.redirect import (
    RedirectError,
    LinkPasswordRequired,
    resolve_redirect,
)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

PASSWORD_PROMPT_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Protected link - {app_name}</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#f8fafc;
      display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
 .card{{background:#1e293b;padding:2rem;border-radius:12px;width:100%;max-width:380px}}
 h1{{font-size:1.25rem;margin:0 0 .5rem}}
 p{{color:#94a3b8;font-size:.9rem;margin:0 0 1.5rem}}
 input{{width:100%;padding:.75rem 1rem;margin-bottom:1rem;border:2px solid #334155;border-radius:8px;
        background:#0f172a;color:#f8fafc;font-size:1rem}}
 input:focus{{outline:none;border-color:#6366f1}}
 button{{width:100%;padding:.75rem;background:#6366f1;color:#fff;border:none;border-radius:8px;
         font-size:1rem;font-weight:600;cursor:pointer}}
 button:hover{{background:#4f46e5}}
 .error{{color:#ef4444;font-size:.85rem;margin-bottom:1rem}}
</style></head>
<body><div class="card">
 <h1>This link is password protected</h1>
 <p>Enter the password to continue to <code>{short_code}</code>.</p>
 {error}
 <form method="get" action="/{short_code}">
   <input type="password" name="password" placeholder="Password" autofocus required>
   <button type="submit">Unlock</button>
 </form>
</div></body></html>"""


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown hooks."""
    settings.validate_runtime()

    if settings.DEBUG or not settings.is_production:
        # Production deployments run `alembic upgrade head` instead.
        try:
            from app.db.models import Base

            Base.metadata.create_all(bind=engine)
            logger.info("Database tables ensured")
        except Exception as exc:
            logger.error("Could not create database tables: %s", exc)

    logger.info(
        "%s %s started (environment=%s, click_mode=%s)",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.click_write_mode,
    )
    yield
    logger.info("%s shutting down", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "URL shortener with Redis-backed redirects, click analytics, "
        "JWT authentication and per-route rate limiting."
    ),
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
if settings.trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(auth.router)
app.include_router(links.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(qr.router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Attach a correlation id to every request and response."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", tags=["ops"])
def health_check():
    """Readiness probe that actually checks the dependencies.

    The previous implementation always returned ``200 healthy`` even when
    every database-backed route returned 500, which made the platform
    route traffic to a broken instance.
    """
    checks: dict[str, str] = {"database": "ok", "redis": "ok"}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    if not redis_healthy():
        # Redis is optional: the app degrades to database-only mode.
        checks["redis"] = "unavailable"

    healthy = checks["database"] == "ok"
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        },
    )


@app.get("/", response_class=HTMLResponse, tags=["web"])
def home(request: Request):
    """Landing page."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": settings.APP_NAME},
    )


@app.get("/dashboard", response_class=HTMLResponse, tags=["web"])
def dashboard(request: Request):
    """Dashboard page."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "app_name": settings.APP_NAME},
    )


# NOTE: this catch-all must stay last so that it cannot shadow /docs,
# /health, /dashboard, /static or any /api route.
@app.get("/{short_code}", tags=["redirect"])
def redirect_short_code(
    short_code: str,
    request: Request,
    password: str | None = None,
):
    """Redirect a short code to its destination.

    This is the product: the URL that was handed to the user resolves
    here. Reads the destination from Redis (cache-aside), records the
    click and issues a 307 so the HTTP method and body are preserved.
    """
    db = next(get_db())
    try:
        try:
            target = resolve_redirect(db, short_code, password)
        except RedirectError as exc:
            if isinstance(exc, LinkPasswordRequired):
                error = (
                    '<p class="error">That password is not correct.</p>'
                    if password
                    else ""
                )
                return HTMLResponse(
                    content=PASSWORD_PROMPT_TEMPLATE.format(
                        app_name=settings.APP_NAME,
                        short_code=short_code,
                        error=error,
                    ),
                    status_code=exc.status_code,
                )
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

        record_click(db, build_click_event(request, target.link_id, target.short_code))
    finally:
        db.close()

    return RedirectResponse(url=target.original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
