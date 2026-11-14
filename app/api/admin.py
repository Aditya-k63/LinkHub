"""Administrative endpoints (platform owner only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.db.models import Click, Link, User
from app.db.session import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def admin_stats(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Platform-wide counters and the most-clicked links."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_links = db.query(func.count(Link.id)).scalar() or 0
    total_clicks = db.query(func.count(Click.id)).scalar() or 0
    active_links = (
        db.query(func.count(Link.id)).filter(Link.is_active.is_(True)).scalar() or 0
    )

    top_links = (
        db.query(Link.short_code, Link.click_count, Link.original_url)
        .order_by(Link.click_count.desc())
        .limit(10)
        .all()
    )

    return {
        "total_users": total_users,
        "total_links": total_links,
        "total_clicks": total_clicks,
        "active_links": active_links,
        "top_links": [
            {"short_code": row.short_code, "clicks": row.click_count, "url": row.original_url}
            for row in top_links
        ],
    }


@router.get("/users")
def admin_users(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List every registered user."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {
        "users": [
            {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "created_at": user.created_at.isoformat(),
            }
            for user in users
        ]
    }
