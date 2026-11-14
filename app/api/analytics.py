"""Click analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.identifiers import to_uuid
from app.db.models import Link, User
from app.db.session import get_db
from app.services.analytics import get_link_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/{link_id}")
def link_analytics(
    link_id: str,
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return click analytics for a link owned by the authenticated user."""
    identifier = to_uuid(link_id)
    if identifier is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed link id")

    link = db.query(Link).filter(Link.id == identifier, Link.owner_id == user.id).first()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    analytics = get_link_analytics(db, identifier, days)
    analytics["link"] = {
        "id": str(link.id),
        "short_code": link.short_code,
        "original_url": link.original_url,
        "title": link.title,
    }
    return analytics


@router.get("/{link_id}/series")
def link_series(
    link_id: str,
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return the daily click series for a link (used by the dashboard chart)."""
    identifier = to_uuid(link_id)
    if identifier is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed link id")

    link = db.query(Link).filter(Link.id == identifier, Link.owner_id == user.id).first()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    analytics = get_link_analytics(db, identifier, days)
    return {
        "link_id": str(link.id),
        "days": days,
        "daily_clicks": analytics["daily_clicks"],
        "total_clicks": analytics["total_clicks"],
    }
