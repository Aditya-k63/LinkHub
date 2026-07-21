from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            from app.services.redis_cache import check_rate_limit, redis_client
            if redis_client:
                client_ip = request.client.host
                if not check_rate_limit(client_ip):
                    raise HTTPException(status_code=429, detail="Too many requests")
        except Exception:
            pass

        response = await call_next(request)
        return response
