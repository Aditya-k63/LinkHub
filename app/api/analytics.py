from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Link
from app.services.analytics import get_link_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/{link_id}")
def get_analytics(link_id: str, request: Request, days: int = 30, db: Session = Depends(get_db)):
    user_id = request.state.user_id
    link = db.query(Link).filter(Link.id == link_id, Link.owner_id == user_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    analytics = get_link_analytics(db, link_id, days)
    analytics["link"] = {
        "id": str(link.id),
        "short_code": link.short_code,
        "original_url": link.original_url,
        "title": link.title,
    }

    return analytics
