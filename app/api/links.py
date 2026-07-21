from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime
from app.db.session import get_db
from app.db.models import Link, User
from app.services.shortener import create_short_code, get_link_by_code
from app.services.redis_cache import cache_link, get_cached_link, invalidate_link_cache
from app.services.qr_service import generate_qr_code
from app.core.config import settings
from app.core.logger import logger

router = APIRouter(prefix="/api/links", tags=["links"])


class CreateLinkRequest(BaseModel):
    url: HttpUrl
    custom_alias: Optional[str] = None
    title: Optional[str] = None
    password: Optional[str] = None
    expires_in_hours: Optional[int] = None


class LinkResponse(BaseModel):
    id: str
    short_code: str
    short_url: str
    original_url: str
    title: Optional[str]
    click_count: int
    created_at: str
    expires_at: Optional[str]
    qr_code: str


class UpdateLinkRequest(BaseModel):
    original_url: Optional[HttpUrl] = None
    title: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("", response_model=LinkResponse)
def create_link(request: CreateLinkRequest, req: Request, db: Session = Depends(get_db)):
    user_id = req.state.user_id

    try:
        short_code = create_short_code(db, request.custom_alias)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    expires_at = None
    if request.expires_in_hours:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours)

    password_hash = None
    if request.password:
        from app.core.security import get_password_hash
        password_hash = get_password_hash(request.password)

    link = Link(
        short_code=short_code,
        original_url=str(request.url),
        title=request.title,
        password_hash=password_hash,
        expires_at=expires_at,
        owner_id=user_id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    cache_link(short_code, str(request.url))

    base_url = settings.BASE_URL or "http://localhost:8000"
    short_url = f"{base_url}/{short_code}"
    qr_code = generate_qr_code(short_url)

    logger.info(f"Link created: {short_code} -> {request.url}")

    return LinkResponse(
        id=str(link.id),
        short_code=link.short_code,
        short_url=short_url,
        original_url=link.original_url,
        title=link.title,
        click_count=link.click_count,
        created_at=link.created_at.isoformat(),
        expires_at=link.expires_at.isoformat() if link.expires_at else None,
        qr_code=qr_code,
    )


@router.get("/{short_code}")
def redirect_link(short_code: str, password: str = None, db: Session = Depends(get_db)):
    cached_url = get_cached_link(short_code)
    if cached_url:
        link = get_link_by_code(db, short_code)
        if not link or not link.is_active:
            raise HTTPException(status_code=404, detail="Link not found")

        if link.expires_at and link.expires_at < datetime.utcnow():
            raise HTTPException(status_code=410, detail="Link has expired")

        if link.password_hash:
            from app.core.security import verify_password
            if not password or not verify_password(password, link.password_hash):
                raise HTTPException(status_code=403, detail="Password required")

        from app.services.redis_cache import push_click_event
        push_click_event({"link_id": str(link.id), "short_code": short_code})

        return {"redirect_url": cached_url}

    link = get_link_by_code(db, short_code)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Link has expired")

    if link.password_hash:
        from app.core.security import verify_password
        if not password or not verify_password(password, link.password_hash):
            raise HTTPException(status_code=403, detail="Password required")

    cache_link(short_code, link.original_url)

    from app.services.redis_cache import push_click_event
    push_click_event({"link_id": str(link.id), "short_code": short_code})

    return {"redirect_url": link.original_url}


@router.get("")
def list_links(request: Request, page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    user_id = request.state.user_id
    offset = (page - 1) * limit

    links = db.query(Link).filter(Link.owner_id == user_id).offset(offset).limit(limit).all()
    total = db.query(Link).filter(Link.owner_id == user_id).count()

    base_url = settings.BASE_URL or "http://localhost:8000"

    return {
        "links": [
            {
                "id": str(link.id),
                "short_code": link.short_code,
                "short_url": f"{base_url}/{link.short_code}",
                "original_url": link.original_url,
                "title": link.title,
                "click_count": link.click_count,
                "created_at": link.created_at.isoformat(),
            }
            for link in links
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.put("/{link_id}")
def update_link(link_id: str, request: UpdateLinkRequest, req: Request, db: Session = Depends(get_db)):
    user_id = req.state.user_id
    link = db.query(Link).filter(Link.id == link_id, Link.owner_id == user_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    if request.original_url:
        link.original_url = str(request.original_url)
        invalidate_link_cache(link.short_code)
        cache_link(link.short_code, link.original_url)

    if request.title is not None:
        link.title = request.title

    if request.is_active is not None:
        link.is_active = request.is_active
        if not request.is_active:
            invalidate_link_cache(link.short_code)

    db.commit()
    logger.info(f"Link updated: {link.short_code}")
    return {"message": "Link updated"}


@router.delete("/{link_id}")
def delete_link(link_id: str, request: Request, db: Session = Depends(get_db)):
    user_id = request.state.user_id
    link = db.query(Link).filter(Link.id == link_id, Link.owner_id == user_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    invalidate_link_cache(link.short_code)
    db.delete(link)
    db.commit()

    logger.info(f"Link deleted: {link.short_code}")
    return {"message": "Link deleted"}
