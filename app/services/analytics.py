from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.db.models import Click, Link


def log_click(db: Session, link_id: str, click_data: dict) -> None:
    click = Click(
        link_id=link_id,
        ip_address=click_data.get("ip_address"),
        user_agent=click_data.get("user_agent"),
        referrer=click_data.get("referrer"),
        country=click_data.get("country"),
        city=click_data.get("city"),
        browser=click_data.get("browser"),
        os=click_data.get("os"),
        device_type=click_data.get("device_type"),
    )
    db.add(click)

    link = db.query(Link).filter(Link.id == link_id).first()
    if link:
        link.click_count += 1

    db.commit()


def get_link_analytics(db: Session, link_id: str, days: int = 30) -> dict:
    since = datetime.utcnow() - timedelta(days=days)

    total_clicks = db.query(func.count(Click.id)).filter(
        Click.link_id == link_id,
        Click.clicked_at >= since,
    ).scalar()

    daily_clicks = (
        db.query(
            func.date(Click.clicked_at).label("date"),
            func.count(Click.id).label("count"),
        )
        .filter(Click.link_id == link_id, Click.clicked_at >= since)
        .group_by(func.date(Click.clicked_at))
        .order_by(func.date(Click.clicked_at))
        .all()
    )

    top_countries = (
        db.query(Click.country, func.count(Click.id).label("count"))
        .filter(Click.link_id == link_id, Click.country.isnot(None))
        .group_by(Click.country)
        .order_by(func.count(Click.id).desc())
        .limit(10)
        .all()
    )

    top_browsers = (
        db.query(Click.browser, func.count(Click.id).label("count"))
        .filter(Click.link_id == link_id, Click.browser.isnot(None))
        .group_by(Click.browser)
        .order_by(func.count(Click.id).desc())
        .limit(10)
        .all()
    )

    top_devices = (
        db.query(Click.device_type, func.count(Click.id).label("count"))
        .filter(Click.link_id == link_id, Click.device_type.isnot(None))
        .group_by(Click.device_type)
        .order_by(func.count(Click.id).desc())
        .limit(10)
        .all()
    )

    top_referrers = (
        db.query(Click.referrer, func.count(Click.id).label("count"))
        .filter(Click.link_id == link_id, Click.referrer.isnot(None))
        .group_by(Click.referrer)
        .order_by(func.count(Click.id).desc())
        .limit(10)
        .all()
    )

    return {
        "total_clicks": total_clicks,
        "daily_clicks": [{"date": str(d.date), "clicks": d.count} for d in daily_clicks],
        "top_countries": [{"country": c.country, "clicks": c.count} for c in top_countries],
        "top_browsers": [{"browser": b.browser, "clicks": b.count} for b in top_browsers],
        "top_devices": [{"device": d.device_type, "clicks": d.count} for d in top_devices],
        "top_referrers": [{"referrer": r.referrer, "clicks": r.count} for r in top_referrers],
    }
