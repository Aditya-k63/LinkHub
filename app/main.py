import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import uuid
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from app.core.config import settings

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
    except Exception as e:
        print(f"Database startup error: {e}")

try:
    from app.middleware.rate_limit import RateLimitMiddleware
    from app.middleware.auth import AuthMiddleware
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)
except Exception as e:
    print(f"Middleware error: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from app.api import auth, links, analytics, admin
    app.include_router(auth.router)
    app.include_router(links.router)
    app.include_router(analytics.router)
    app.include_router(admin.router)
except Exception as e:
    print(f"Router error: {e}")

static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir)) if templates_dir.exists() else None


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if templates:
        return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.APP_NAME})
    return HTMLResponse("<h1>LinkHub</h1><p><a href='/docs'>API Docs</a></p>")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if templates:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return HTMLResponse("<h1>Dashboard</h1>")


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}
