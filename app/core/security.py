"""Password hashing and JWT helpers.

Uses PyJWT rather than python-jose: python-jose 3.3.0 (which this project
previously pinned) is affected by CVE-2024-33663 and CVE-2024-33664.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        # Malformed hash in the database - treat as a failed login rather
        # than a 500.
        return False


def get_password_hash(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Issue a signed JWT carrying ``data`` plus ``exp``/``iat`` claims."""
    to_encode = dict(data)
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and verify a JWT.

    Returns ``None`` for anything that is not a valid, unexpired token
    signed with the configured secret. ``algorithms`` is pinned so a token
    can never select its own verification algorithm.
    """
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except InvalidTokenError:
        return None
