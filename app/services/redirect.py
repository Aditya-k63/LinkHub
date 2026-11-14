"""Redirect resolution shared by the public route and the JSON API.

The hot path reads the link metadata from Redis (cache-aside). On a cache
miss the database is consulted and the cache is repopulated. Expiry,
password protection and click recording are handled here so that both
entry points behave identically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.core.security import verify_password
from app.db.models import Link, utcnow
from app.services.redis_cache import (
    cache_link_record,
    get_cached_link_record,
    invalidate_link_cache,
)
from app.services.shortener import get_link_by_code


class RedirectError(Exception):
    """Base class for redirect failures."""

    status_code = 404
    detail = "Link not found"


class LinkNotFound(RedirectError):
    status_code = 404
    detail = "Link not found"


class LinkInactive(RedirectError):
    status_code = 404
    detail = "Link is disabled"


class LinkExpired(RedirectError):
    status_code = 410
    detail = "Link has expired"


class LinkPasswordRequired(RedirectError):
    status_code = 403
    detail = "This link is password protected"


@dataclass(frozen=True)
class RedirectTarget:
    """Everything the caller needs to issue a redirect and record a click."""

    link_id: str
    short_code: str
    original_url: str
    expires_at: Optional[datetime]
    from_cache: bool


def _as_payload(link: Link) -> dict:
    return {
        "id": str(link.id),
        "short_code": link.short_code,
        "original_url": link.original_url,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "password_hash": link.password_hash,
        "is_active": link.is_active,
    }


def warm_cache(link: Link) -> None:
    """Populate the redirect cache for ``link``."""
    cache_link_record(link.short_code, _as_payload(link))


def drop_cache(short_code: str) -> None:
    """Remove ``short_code`` from the redirect cache."""
    invalidate_link_cache(short_code)


def _parse_expiry(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def resolve_redirect(
    db: Session, short_code: str, password: Optional[str] = None
) -> RedirectTarget:
    """Resolve ``short_code`` to its destination.

    Raises a :class:`RedirectError` subclass when the link cannot be
    followed.
    """
    payload = get_cached_link_record(short_code)
    from_cache = payload is not None

    if payload is None:
        link = get_link_by_code(db, short_code)
        if link is None:
            raise LinkNotFound()
        payload = _as_payload(link)
        warm_cache(link)

    if not payload.get("is_active", True):
        raise LinkInactive()

    expires_at = _parse_expiry(payload.get("expires_at"))
    if expires_at is not None and expires_at <= utcnow():
        raise LinkExpired()

    password_hash = payload.get("password_hash")
    if password_hash:
        if not password or not verify_password(password, password_hash):
            raise LinkPasswordRequired()

    return RedirectTarget(
        link_id=str(payload["id"]),
        short_code=payload["short_code"],
        original_url=payload["original_url"],
        expires_at=expires_at,
        from_cache=from_cache,
    )
