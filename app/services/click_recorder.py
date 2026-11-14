"""Click persistence.

In ``sync`` mode the click is written inline so the counter is correct
immediately and the feature works with no extra infrastructure. In
``async`` mode the event is pushed onto Redis and a worker persists it, so
the redirect path does not block on a database write.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import to_uuid
from app.core.logger import logger
from app.db.models import Click, Link
from app.services.redis_cache import push_click_event, redis_client


def persist_click(db: Session, event: dict[str, Any]) -> None:
    """Write a click row and bump the link's counter."""
    link_id = to_uuid(event.get("link_id"))
    if link_id is None:
        logger.warning("Discarding click with invalid link_id: %r", event.get("link_id"))
        return

    click = Click(
        link_id=link_id,
        ip_address=event.get("ip_address"),
        user_agent=event.get("user_agent"),
        referrer=event.get("referrer"),
        country=event.get("country"),
        city=event.get("city"),
        browser=event.get("browser"),
        os=event.get("os"),
        device_type=event.get("device_type"),
        is_bot=bool(event.get("is_bot", False)),
    )
    db.add(click)

    # A single UPDATE avoids a read-modify-write round trip.
    db.query(Link).filter(Link.id == link_id).update(
        {Link.click_count: Link.click_count + 1},
        synchronize_session=False,
    )
    db.commit()


def record_click(db: Session, event: dict[str, Any]) -> None:
    """Record a click according to the configured write mode."""
    # Async mode needs a queue. Without Redis there is nowhere to put the
    # event, so fall back to writing it inline rather than losing it.
    if settings.click_write_mode == "async" and redis_client is not None:
        push_click_event(event)
        return

    try:
        persist_click(db, event)
    except Exception as exc:
        # A failed analytics write must never break a redirect.
        db.rollback()
        logger.warning("Could not persist click: %s", exc)


def drain_queued_clicks(db: Session, max_events: int | None = None) -> int:
    """Persist queued click events (used by the worker)."""
    from app.services.redis_cache import pop_click_event

    processed = 0
    while max_events is None or processed < max_events:
        event = pop_click_event(timeout=1)
        if event is None:
            break
        try:
            persist_click(db, event)
        except Exception as exc:
            db.rollback()
            logger.warning("Could not persist queued click: %s", exc)
        processed += 1
    return processed
