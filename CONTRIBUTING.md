# Contributing to LinkHub

Thanks for taking the time to contribute. This document explains how to get
the project running locally and what is expected of a pull request.

## Getting set up

```bash
git clone https://github.com/Aditya-k63/LinkHub.git
cd LinkHub

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env      # Windows: copy .env.example .env
```

Edit `.env` and set at least `SECRET_KEY` and `JWT_SECRET_KEY`. Any value
works for local development:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Running the app

```bash
# SQLite only - no servers required
uvicorn app.main:app --reload
```

```bash
# With PostgreSQL and Redis
docker compose up --build
```

```bash
# The click worker (only needed for CLICK_WRITE_MODE=async)
python -m app.workers.consumer
```

The application is then available on <http://localhost:8000> with the
interactive API docs at <http://localhost:8000/docs>.

## Running the tests

```bash
pytest                      # the whole suite
pytest --cov=app            # with a coverage report
python scripts/smoke_test.py  # end-to-end check of the product flow
```

The suite runs against an in-memory SQLite database and never touches a real
database or Redis instance.

## Code style

```bash
ruff check .        # lint
ruff format .       # format
mypy app            # type check
```

All three run in CI, so a pull request that fails them will not merge.

- Line length is 100 characters.
- Type hints on every public function.
- Docstrings explain *why*, not *what*.

## Making a change

1. Branch off `main`: `git checkout -b feature/short-description`
2. Make the change, and add a test that fails without it.
3. Run `pytest`, `ruff check .` and `mypy app`.
4. Open a pull request describing what changed and why.

### Database changes

The schema is owned by Alembic. After changing a model:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Commit both the model change and the generated migration. Never edit an
already-applied migration - add a new one instead.

## Commit messages

Use the imperative mood and explain the reason for the change:

```
fix: return 401 instead of 500 on unauthenticated writes
```

## Reporting bugs

Open an issue with the request, the response, the steps to reproduce and the
relevant log lines. Logs are JSON, so pasting them is enough.
