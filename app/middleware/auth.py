from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.security import decode_access_token
from app.core.logger import logger

EXEMPT_PATHS = ["/", "/docs", "/openapi.json", "/redoc", "/login", "/register", "/health"]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS or request.url.path.startswith("/static"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            if request.url.path.startswith("/api/"):
                raise HTTPException(status_code=401, detail="Missing authorization header")
            return await call_next(request)

        token = auth_header.split(" ")[1]
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        request.state.user_id = payload.get("sub")
        request.state.is_admin = payload.get("is_admin", False)

        return await call_next(request)
