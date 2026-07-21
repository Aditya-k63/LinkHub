import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import uuid
from contextvars import ContextVar
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logger import logger, request_id_var
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.auth import AuthMiddleware
from app.api import auth, links, analytics, admin

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready URL shortening service with analytics",
)

@app.on_event("startup")
async def startup():
    try:
        from app.db.session import engine
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")
    except Exception as e:
        logger.error(f"Database startup error: {e}")

app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(links.router)
app.include_router(analytics.router)
app.include_router(admin.router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>LinkHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { text-align: center; max-width: 600px; padding: 2rem; }
        h1 { font-size: 3rem; margin-bottom: 1rem; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        p { color: #94a3b8; font-size: 1.2rem; margin-bottom: 2rem; }
        a { color: #6366f1; text-decoration: none; font-size: 1.1rem; border: 2px solid #6366f1; padding: 0.75rem 2rem; border-radius: 8px; transition: all 0.2s; }
        a:hover { background: #6366f1; color: white; }
    </style>
    </head>
    <body>
    <div class="container">
        <h1>LinkHub</h1>
        <p>Production-ready URL shortener with analytics, caching, and rate limiting.</p>
        <a href="/docs">View API Docs</a>
    </div>
    </body>
    </html>
    """)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return HTMLResponse("<h1>Dashboard - Coming Soon</h1><p><a href='/'>Home</a></p>")


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} started")
