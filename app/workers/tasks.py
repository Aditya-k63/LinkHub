"""Background tasks.

These are only executed by a worker process:

    celery -A app.workers.celery worker --loglevel=info
    celery -A app.workers.celery beat --loglevel=info
"""

from __future__ import annotations

from app.core.logger import logger
from app.db.models import Link, utcnow
from app.db.session import SessionLocal
from app.services.analytics import get_platform_summary
from app.services.click_recorder import drain_queued_clicks
from app.workers.celery import celery_app


@celery_app.task(name="linkhub.process_click")
def process_click(click_data: dict) -> None:
    """Persist a single click event."""
    db = SessionLocal()
    try:
        from app.services.click_recorder import persist_click

        persist_click(db, click_data)
        logger.info("Processed click for link %s", click_data.get("short_code"))
    except Exception as exc:
        db.rollback()
        logger.error("Failed to process click: %s", exc)
    finally:
        db.close()


@celery_app.task(name="linkhub.drain_click_queue")
def drain_click_queue(max_events: int | None = None) -> int:
    """Persist every click currently sitting on the Redis queue."""
    db = SessionLocal()
    try:
        processed = drain_queued_clicks(db, max_events=max_events)
        if processed:
            logger.info("Persisted %s queued clicks", processed)
        return processed
    finally:
        db.close()


@celery_app.task(name="linkhub.cleanup_expired_links")
def cleanup_expired_links() -> int:
    """Deactivate links whose expiry date has passed."""
    db = SessionLocal()
    try:
        expired = (
            db.query(Link)
            .filter(
                Link.expires_at.isnot(None),
                Link.expires_at < utcnow(),
                Link.is_active.is_(True),
            )
            .all()
        )

        for link in expired:
            link.is_active = False
            logger.info("Deactivated expired link %s", link.short_code)

        db.commit()
        return len(expired)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to clean up expired links: %s", exc)
        return 0
    finally:
        db.close()


@celery_app.task(name="linkhub.aggregate_daily_stats")
def aggregate_daily_stats() -> dict:
    """Summarise the last day of activity."""
    db = SessionLocal()
    try:
        summary = get_platform_summary(db, days=1)
        logger.info("Daily stats: %s", summary)
        return summary
    finally:
        db.close()
