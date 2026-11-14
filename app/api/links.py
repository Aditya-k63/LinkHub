"""Link management endpoints."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.identifiers import to_uuid
from app.core.logger import logger
from app.db.models import Link, User, utcnow
from app.db.session import get_db
from app.services.click_recorder import record_click
from app.services.click_tracker import build_click_event
from app.services.qr_service import generate_qr_code
from app.services.redirect import (
    RedirectError,
    drop_cache,
    resolve_redirect,
    warm_cache,
)
from app.services.shortener import InvalidAliasError, create_short_code, get_link_by_code

router = APIRouter(prefix="/api/links", tags=["links"])

MAX_TTL_HOURS = 24 * 365


class CreateLinkRequest(BaseModel):
    url: HttpUrl
    custom_alias: Optional[str] = Field(default=None, max_length=10)
    title: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, max_length=128)
    expires_in_hours: Optional[int] = Field(default=None, gt=0, le=MAX_TTL_HOURS)


class UpdateLinkRequest(BaseModel):
    original_url: Optional[HttpUrl] = None
    title: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None
    expires_in_hours: Optional[int] = Field(default=None, gt=0, le=MAX_TTL_HOURS)


class LinkResponse(BaseModel):
    id: str
    short_code: str
    short_url: str
    original_url: str
    title: Optional[str] = None
    click_count: int
    created_at: str
    expires_at: Optional[str] = None
    is_active: bool
    qr_code: str


class LinkSummary(BaseModel):
    id: str
    short_code: str
    short_url: str
    original_url: str
    title: Optional[str] = None
    click_count: int
    created_at: str
    expires_at: Optional[str] = None
    is_active: bool


class LinkListResponse(BaseModel):
    links: list[LinkSummary]
    total: int
    page: int
    limit: int


def _short_url(short_code: str) -> str:
    return f"{settings.public_base_url}/{short_code}"


def _to_summary(link: Link) -> LinkSummary:
    return LinkSummary(
        id=str(link.id),
        short_code=link.short_code,
        short_url=_short_url(link.short_code),
        original_url=link.original_url,
        title=link.title,
        click_count=link.click_count,
        created_at=link.created_at.isoformat(),
        expires_at=link.expires_at.isoformat() if link.expires_at else None,
        is_active=link.is_active,
    )


@router.post("", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(
    payload: CreateLinkRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LinkResponse:
    """Create a short link."""
    try:
        short_code = create_short_code(db, payload.custom_alias)
    except InvalidAliasError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    expires_at = None
    if payload.expires_in_hours:
        expires_at = utcnow() + timedelta(hours=payload.expires_in_hours)

    password_hash = None
    if payload.password:
        from app.core.security import get_password_hash

        password_hash = get_password_hash(payload.password)

    link = Link(
        short_code=short_code,
        original_url=str(payload.url),
        title=payload.title,
        password_hash=password_hash,
        expires_at=expires_at,
        owner_id=user.id,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race for the unique short code - report it rather than 500.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That short code was just taken, please try again",
        )
    db.refresh(link)

    warm_cache(link)
    short_url = _short_url(link.short_code)

    logger.info("Created link %s for user %s", link.short_code, user.username)

    return LinkResponse(
        id=str(link.id),
        short_code=link.short_code,
        short_url=short_url,
        original_url=link.original_url,
        title=link.title,
        click_count=link.click_count,
        created_at=link.created_at.isoformat(),
        expires_at=link.expires_at.isoformat() if link.expires_at else None,
        is_active=link.is_active,
        qr_code=generate_qr_code(short_url),
    )


@router.get("", response_model=LinkListResponse)
def list_links(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LinkListResponse:
    """List the links owned by the authenticated user."""
    query = db.query(Link).filter(Link.owner_id == user.id)
    total = query.count()
    links = (
        query.order_by(Link.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return LinkListResponse(
        links=[_to_summary(link) for link in links],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{short_code}")
def resolve_link(
    short_code: str,
    request: Request,
    password: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Resolve a short code to its destination and record the click.

    This is the JSON twin of ``GET /{short_code}`` and exists for clients
    that want the destination without following the redirect.
    """
    try:
        target = resolve_redirect(db, short_code, password)
    except RedirectError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    record_click(db, build_click_event(request, target.link_id, target.short_code))

    return {
        "short_code": target.short_code,
        "redirect_url": target.original_url,
        "expires_at": target.expires_at.isoformat() if target.expires_at else None,
    }


@router.put("/{link_id}")
def update_link(
    link_id: str,
    payload: UpdateLinkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Update a link owned by the authenticated user."""
    identifier = to_uuid(link_id)
    if identifier is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed link id"
        )

    link = (
        db.query(Link)
        .filter(Link.id == identifier, Link.owner_id == user.id)
        .first()
    )
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    if payload.original_url is not None:
        link.original_url = str(payload.original_url)
    if payload.title is not None:
        link.title = payload.title
    if payload.is_active is not None:
        link.is_active = payload.is_active
    if payload.expires_in_hours is not None:
        link.expires_at = utcnow() + timedelta(hours=payload.expires_in_hours)

    db.commit()
    db.refresh(link)

    # The cached copy is now stale.
    drop_cache(link.short_code)
    if link.is_active:
        warm_cache(link)

    logger.info("Updated link %s", link.short_code)
    return {"message": "Link updated", **_to_summary(link).model_dump()}


@router.delete("/{link_id}")
def delete_link(
    link_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Delete a link owned by the authenticated user."""
    identifier = to_uuid(link_id)
    if identifier is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed link id"
        )

    link = (
        db.query(Link)
        .filter(Link.id == identifier, Link.owner_id == user.id)
        .first()
    )
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    drop_cache(link.short_code)
    db.delete(link)
    db.commit()

    logger.info("Deleted link %s", link.short_code)
    return {"message": "Link deleted"}


@router.get("/{short_code}/exists")
def link_exists(short_code: str, db: Session = Depends(get_db)) -> dict:
    """Report whether a short code can be used (used by the alias field)."""
    link = get_link_by_code(db, short_code, include_inactive=True)
    return {"available": link is None, "short_code": short_code}
