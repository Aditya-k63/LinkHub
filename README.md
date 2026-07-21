# LinkHub — Production-Ready URL Shortener & Analytics Platform

A production-ready URL shortening service with analytics, authentication, caching, rate limiting, and QR code generation.

## Features

- **JWT Authentication** — Secure user registration and login
- **URL Shortening** — Create short URLs with custom aliases
- **QR Code Generation** — Auto-generated QR codes for every link
- **Redis Caching** — Sub-5ms redirect lookups
- **Rate Limiting** — Redis-based abuse prevention
- **Click Analytics** — Track clicks, devices, browsers, geography
- **URL Expiration** — TTL-based auto-deletion
- **Password-Protected Links** — Optional password requirement
- **Background Workers** — Celery for async analytics processing
- **Structured Logging** — Request IDs, timestamps, log levels
- **CI/CD** — GitHub Actions for testing and deployment

## Architecture

```
Client
   │
FastAPI Backend
   │
   ├─ PostgreSQL (persistence)
   ├─ Redis (caching + rate limiting)
   ├─ Celery Worker (background tasks)
   └─ Nginx (reverse proxy)
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, Python 3.12 |
| Database | PostgreSQL + SQLAlchemy |
| Cache | Redis |
| Task Queue | Celery + Redis |
| Auth | JWT (python-jose) |
| CI/CD | GitHub Actions |
| Deployment | Render / Railway / Fly.io |

## Quick Start (Local)

```bash
# Clone
git clone https://github.com/yourusername/linkhub.git
cd linkhub

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env

# Run PostgreSQL and Redis (or use Docker)
# PostgreSQL: localhost:5432
# Redis: localhost:6379

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload

# Access
# Web UI: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Deployment (No Docker Required)

### Option 1: Render (Recommended)

1. Push to GitHub
2. Go to [render.com](https://render.com)
3. Create new PostgreSQL database
4. Create new Redis instance
5. Create new Web Service
6. Connect your GitHub repo
7. Set environment variables:
   ```
   DATABASE_URL=<from PostgreSQL>
   REDIS_URL=<from Redis>
   JWT_SECRET_KEY=<random-string>
   SECRET_KEY=<random-string>
   BASE_URL=<your-render-url>
   ```
8. Deploy

### Option 2: Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app)
3. New Project → Deploy from GitHub
4. Add PostgreSQL and Redis plugins
5. Set environment variables
6. Deploy

### Option 3: Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Launch
fly launch

# Deploy
fly deploy
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| POST | `/api/links` | Create short URL |
| GET | `/{short_code}` | Redirect to original URL |
| GET | `/api/links` | List user's links |
| PUT | `/api/links/{id}` | Update link |
| DELETE | `/api/links/{id}` | Delete link |
| GET | `/api/analytics/{link_id}` | Get link analytics |
| GET | `/api/admin/stats` | Admin dashboard stats |

## Database Schema

```
users
├── id (UUID)
├── email (unique)
├── username (unique)
├── hashed_password
├── is_active
├── is_admin
└── created_at

links
├── id (UUID)
├── short_code (unique)
├── original_url
├── title
├── password_hash
├── expires_at
├── click_count
├── owner_id (FK → users)
└── created_at

clicks
├── id (UUID)
├── link_id (FK → links)
├── clicked_at
├── ip_address
├── user_agent
├── referrer
├── country
├── browser
├── os
└── device_type
```

## Project Structure

```
LinkHub/
├── app/
│   ├── api/           # Route handlers
│   ├── core/          # Config, security, logging
│   ├── db/            # Database models and session
│   ├── services/      # Business logic
│   ├── middleware/     # Auth, rate limiting
│   ├── workers/       # Celery tasks
│   └── main.py        # FastAPI app
├── tests/             # Test suite
├── nginx/             # Nginx config
├── static/            # CSS, JS
├── templates/         # HTML templates
├── .github/workflows  # CI/CD
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## CI/CD

GitHub Actions runs on every push:
- **Lint**: ruff check
- **Test**: pytest with 80%+ coverage
- **Deploy**: Auto-deploy to Render/Railway/Fly.io

## License

MIT
