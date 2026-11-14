"""Celery application.

Celery is optional: it is only needed when ``CLICK_WRITE_MODE=async`` and a
worker process is running. The API itself never imports this module.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "linkhub",
    broker=settings.CELERY_BROKER_URL or "memory://",
    backend=settings.CELERY_RESULT_BACKEND or "cache+memory://",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    worker_prefetch_multiplier=1,
    task_default_queue="linkhub",
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-links-hourly": {
        "task": "linkhub.cleanup_expired_links",
        "schedule": crontab(minute=0),
    },
    "aggregate-daily-stats-daily": {
        "task": "linkhub.aggregate_daily_stats",
        "schedule": crontab(minute=30, hour=0),
    },
}

celery_app.autodiscover_tasks(["app.workers"])
