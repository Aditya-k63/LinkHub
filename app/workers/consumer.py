"""Dependency-free click consumer.

Drains the Redis click queue without needing Celery, which keeps the
async mode usable on platforms where Celery is awkward to run.

    python -m app.workers.consumer
"""

from __future__ import annotations

import signal
import time

from app.core.config import settings
from app.core.logger import logger
from app.db.session import SessionLocal
from app.services.click_recorder import drain_queued_clicks

_running = True


def _stop(signum, frame):  # pragma: no cover - signal handler
    global _running
    logger.info("Consumer received signal %s, shutting down", signum)
    _running = False


def main() -> None:
    """Consume click events until interrupted."""
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info(
        "Click consumer started (mode=%s, broker=%s)",
        settings.click_write_mode,
        "redis" if settings.REDIS_URL else "none",
    )

    while _running:
        db = SessionLocal()
        try:
            processed = drain_queued_clicks(db, max_events=100)
        except Exception as exc:
            logger.error("Consumer error: %s", exc)
            processed = 0
        finally:
            db.close()

        if not processed:
            time.sleep(0.5)

    logger.info("Click consumer stopped")


if __name__ == "__main__":  # pragma: no cover
    main()
