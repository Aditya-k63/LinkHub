"""Short code generation and validation.

Short codes are either a user-chosen alias or a randomly generated one.
Aliases are validated against a strict character set and a list of reserved
words so that a link can never shadow an application route.
"""

from __future__ import annotations

import random
import string

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Link

#: Codes that would collide with an application route.
RESERVED_CODES = frozenset(
    {
        "api",
        "admin",
        "dashboard",
        "docs",
        "favicon.ico",
        "health",
        "login",
        "logout",
        "openapi.json",
        "redoc",
        "register",
        "static",
        "swagger",
    }
)

ALIAS_PATTERN = string.ascii_letters + string.digits + "_-"
MIN_ALIAS_LENGTH = 3
MAX_ALIAS_LENGTH = 10


class InvalidAliasError(ValueError):
    """Raised when a requested alias cannot be used."""


def generate_short_code(length: int | None = None) -> str:
    """Return a random short code."""
    size = length or settings.SHORT_CODE_LENGTH
    size = max(MIN_ALIAS_LENGTH, min(MAX_ALIAS_LENGTH, size))
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=size))


def validate_alias(alias: str) -> str:
    """Validate and normalise a user-chosen alias."""
    candidate = (alias or "").strip()
    if not candidate:
        raise InvalidAliasError("Alias cannot be empty")
    if len(candidate) < MIN_ALIAS_LENGTH:
        raise InvalidAliasError(f"Alias must be at least {MIN_ALIAS_LENGTH} characters long")
    if len(candidate) > MAX_ALIAS_LENGTH:
        raise InvalidAliasError(f"Alias must be at most {MAX_ALIAS_LENGTH} characters long")
    if not all(char in ALIAS_PATTERN for char in candidate):
        raise InvalidAliasError("Alias may only contain letters, numbers, hyphens and underscores")
    if candidate.lower() in RESERVED_CODES:
        raise InvalidAliasError(f"Alias '{candidate}' is reserved")
    return candidate


def get_link_by_code(db: Session, short_code: str, include_inactive: bool = True) -> Link | None:
    """Return the link for ``short_code``, or ``None``."""
    query = db.query(Link).filter(Link.short_code == short_code)
    if not include_inactive:
        query = query.filter(Link.is_active.is_(True))
    return query.first()


def create_short_code(db: Session, custom_alias: str | None = None) -> str:
    """Return an available short code.

    Custom aliases are validated first. Random codes are retried on the
    (rare) unique-constraint collision rather than surfacing an error to
    the caller.
    """
    if custom_alias:
        alias = validate_alias(custom_alias)
        if db.query(Link).filter(Link.short_code == alias).first():
            raise InvalidAliasError(f"Alias '{alias}' is already taken")
        return alias

    for _ in range(10):
        code = generate_short_code()
        if not db.query(Link).filter(Link.short_code == code).first():
            return code

    raise InvalidAliasError("Could not generate a unique short code")


def reserve_short_code(db: Session, code: str) -> bool:
    """Insert a bare link row to reserve ``code`` atomically.

    Returns True when the code was reserved. On a collision the session is
    rolled back and False is returned so the caller can try another code.
    """
    placeholder = Link(short_code=code, original_url="https://placeholder.invalid")
    db.add(placeholder)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    db.delete(placeholder)
    db.commit()
    return True
