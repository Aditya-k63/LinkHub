"""Click analytics aggregation."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Click, Link, utcnow


def get_link_analytics(
    db: Session, link_id: uuid.UUID, days: int = 30, include_bots: bool = False
) -> dict:
    """Aggregate click data for a link over the last ``days`` days."""
    since = utcnow() - timedelta(days=days)

    base = db.query(Click).filter(Click.link_id == link_id)
    human = base.filter(Click.is_bot.is_(False))

    windowed = human.filter(Click.clicked_at >= since)

    total_clicks = windowed.count()
    all_time_clicks = base.count()

    daily_clicks = (
        windowed.with_entities(
            func.date(Click.clicked_at).label("date"),
            func.count(Click.id).label("count"),
        )
        .group_by(func.date(Click.clicked_at))
        .order_by(func.date(Click.clicked_at))
        .all()
    )

    def top_by(column, label):
        rows = (
            windowed.with_entities(column, func.count(Click.id).label("count"))
            .filter(column.isnot(None))
            .group_by(column)
            .order_by(func.count(Click.id).desc())
            .limit(10)
            .all()
        )
        return [{label: row[0], "clicks": row[1]} for row in rows]

    return {
        "window_days": days,
        "total_clicks": total_clicks,
        "all_time_clicks": all_time_clicks,
        "daily_clicks": [{"date": str(row.date), "clicks": row.count} for row in daily_clicks],
        "top_countries": top_by(Click.country, "country"),
        "top_browsers": top_by(Click.browser, "browser"),
        "top_operating_systems": top_by(Click.os, "os"),
        "top_devices": top_by(Click.device_type, "device"),
        "top_referrers": top_by(Click.referrer, "referrer"),
    }


def get_platform_summary(db: Session, days: int = 30) -> dict:
    """Aggregate click data across every link."""
    since = utcnow() - timedelta(days=days)

    total_links = db.query(func.count(Link.id)).scalar() or 0
    total_clicks = db.query(func.count(Click.id)).scalar() or 0
    recent_clicks = db.query(func.count(Click.id)).filter(Click.clicked_at >= since).scalar() or 0
    bot_clicks = db.query(func.count(Click.id)).filter(Click.is_bot.is_(True)).scalar() or 0

    return {
        "total_links": total_links,
        "total_clicks": total_clicks,
        "recent_clicks": recent_clicks,
        "bot_clicks": bot_clicks,
    }
