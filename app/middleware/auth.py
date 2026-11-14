"""Request identity middleware.

Authentication itself is enforced by the dependencies in
:mod:`app.core.deps`. This middleware only decodes the bearer token (when
present) so that the request id / user id can be attached to log lines.
"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.identifiers import to_uuid
from app.core.security import decode_access_token


class AuthMiddleware(BaseHTTPMiddleware):
    """Attach the authenticated user id to the request state, if any."""

    async def dispatch(self, request: Request, call_next):
        request.state.user_id = None
        request.state.is_admin = False

        header = request.headers.get("Authorization")
        if header and header.startswith("Bearer "):
            payload = decode_access_token(header.split(" ", 1)[1])
            if payload:
                user_id = to_uuid(payload.get("sub"))
                request.state.user_id = str(user_id) if user_id else None
                request.state.is_admin = bool(payload.get("is_admin", False))

        return await call_next(request)
