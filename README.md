# LinkHub

A URL shortener I built because I was tired of ugly long links. It does the basics well — shorten URLs, track clicks, generate QR codes — and it's deployed and running live.

**Live:** https://linkhub-4b40.onrender.com

## What it does

- Shorten any URL with a custom alias or let it generate one automatically
- Every link gets a QR code you can download
- Track clicks — browser, device, OS, referrer, country
- Set expiration dates on links so they auto-die
- Password-protect links if you want
- Redis caching so redirects are fast
- Rate limiting so nobody spams your API

## Built with

- **FastAPI** — the backend framework
- **PostgreSQL** — stores everything (using Neon for the hosted instance)
- **Redis** — caching and rate limiting (using Upstash)
- **SQLAlchemy** — ORM
- **JWT** — authentication
- **QRCode + Pillow** — QR code generation
- **GitHub Actions** — CI pipeline that verifies the app builds and Docker image compiles

## Running it locally

```bash
git clone https://github.com/Aditya-k63/LinkHub.git
cd LinkHub
pip install -r requirements.txt
```

You'll need a `.env` file with:

```
DATABASE_URL=sqlite:///./linkhub.db
REDIS_URL=
JWT_SECRET_KEY=any-random-string
SECRET_KEY=another-random-string
BASE_URL=http://localhost:8000
```

For local dev, SQLite works fine without Postgres or Redis. Just leave those empty and the app falls back gracefully.

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000 and you're in.

## Running with Docker

```bash
docker-compose up
```

This spins up the app, Postgres, and Redis. Edit the `.env` file with real credentials if you want persistence.

Or just pull the image:

```bash
docker run -p 8000:8000 <your-username>/linkhub
```

## Project structure

```
LinkHub/
├── app/
│   ├── api/            # auth and link routes
│   ├── core/           # config, security
│   ├── db/             # models and database session
│   ├── middleware/      # auth middleware, rate limiter
│   ├── services/       # redis cache, qr code generation
│   └── main.py         # the FastAPI app with inline frontend
├── .github/workflows/  # CI pipeline
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## API endpoints

| Method | Path | What it does |
|--------|------|--------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get JWT token |
| POST | `/api/links` | Shorten a URL |
| GET | `/{short_code}` | Redirect to original |
| GET | `/api/links` | List your links |
| PUT | `/api/links/{id}` | Update a link |
| DELETE | `/api/links/{id}` | Delete a link |
| GET | `/api/analytics/{link_id}` | Click analytics |
| GET | `/api/admin/stats` | Platform stats |

## How the frontend works

The frontend is inline in `main.py` — no separate React app or build step. It's server-rendered HTML with vanilla JavaScript. Login, register, create links, see your dashboard — all from one page.

## License

MIT
