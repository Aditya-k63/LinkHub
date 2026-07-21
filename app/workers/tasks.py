import json
import redis
from app.workers.celery import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.analytics import log_click
from app.core.logger import logger

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


@celery_app.task(name="process_click")
def process_click(click_data: dict):
    db = SessionLocal()
    try:
        log_click(db, click_data["link_id"], click_data)
        logger.info(f"Click processed for link: {click_data.get('short_code')}")
    except Exception as e:
        logger.error(f"Failed to process click: {e}")
    finally:
        db.close()


@celery_app.task(name="cleanup_expired_links")
def cleanup_expired_links():
    from datetime import datetime
    from app.db.models import Link

    db = SessionLocal()
    try:
        expired = db.query(Link).filter(
            Link.expires_at.isnot(None),
            Link.expires_at < datetime.utcnow(),
            Link.is_active == True,
        ).all()

        for link in expired:
            link.is_active = False
            logger.info(f"Expired link: {link.short_code}")

        db.commit()
        logger.info(f"Cleaned up {len(expired)} expired links")
    finally:
        db.close()


@celery_app.task(name="aggregate_daily_stats")
def aggregate_daily_stats():
    logger.info("Aggregating daily statistics...")
    # Implement daily aggregation logic here
    pass
