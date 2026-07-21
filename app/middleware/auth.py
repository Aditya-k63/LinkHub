from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

EXEMPT_PATHS = ["/", "/docs", "/openapi.json", "/redoc", "/health", "/dashboard"]
EXEMPT_PREFIXES = ["/api/auth/", "/static/"]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in EXEMPT_PATHS:
            return await call_next(request)

        for prefix in EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            request.state.user_id = None
            request.state.is_admin = False
            if path.startswith("/api/"):
                return await call_next(request)
            return await call_next(request)

        token = auth_header.split(" ")[1]
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            if payload:
                request.state.user_id = payload.get("sub")
                request.state.is_admin = payload.get("is_admin", False)
            else:
                request.state.user_id = None
                request.state.is_admin = False
        except Exception:
            request.state.user_id = None
            request.state.is_admin = False

        return await call_next(request)
