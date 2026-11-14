"""Rate limiting middleware.

The previous implementation raised ``HTTPException(429)`` *inside* a
``try: ... except Exception: pass`` block. ``HTTPException`` is a subclass of
``Exception``, so the 429 was always swallowed and the limiter never fired.
The exception is now raised outside the guarded block.
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logger import logger
from app.services.redis_cache import check_rate_limit

# Endpoints that are cheap to serve and would otherwise eat a user's budget.
EXEMPT_PATHS = {"/health", "/favicon.ico", "/openapi.json"}


def client_identifier(request: Request) -> str:
    """Best-effort identity of the caller.

    Behind a reverse proxy ``request.client.host`` is the proxy, so the
    first entry of ``X-Forwarded-For`` is preferred. This trusts the header,
    so it should only be used when the app is known to sit behind a proxy
    that overwrites it.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP request throttling."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in EXEMPT_PATHS or path.startswith("/static/"):
            return await call_next(request)

        # Write endpoints are far more expensive than a redirect, so they
        # get a tighter budget.
        is_write = request.method in {"POST", "PUT", "PATCH", "DELETE"}
        limit = settings.RATE_LIMIT_PER_MINUTE if is_write else settings.RATE_LIMIT_PER_MINUTE * 5

        identifier = client_identifier(request)
        allowed = True
        try:
            allowed = check_rate_limit(identifier, limit=limit)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Rate limiter error, allowing request: %s", exc)

        if not allowed:
            logger.warning("Rate limit exceeded for %s on %s", identifier, path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
