from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import User, Link, Click

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(request: Request):
    if not request.state.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/stats")
def get_admin_stats(request: Request, db: Session = Depends(get_db)):
    require_admin(request)

    total_users = db.query(func.count(User.id)).scalar()
    total_links = db.query(func.count(Link.id)).scalar()
    total_clicks = db.query(func.count(Click.id)).scalar()
    active_links = db.query(func.count(Link.id)).filter(Link.is_active == True).scalar()

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
            {"short_code": l.short_code, "clicks": l.click_count, "url": l.original_url}
            for l in top_links
        ],
    }


@router.get("/users")
def list_users(request: Request, db: Session = Depends(get_db)):
    require_admin(request)

    users = db.query(User).all()
    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "username": u.username,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]
    }
