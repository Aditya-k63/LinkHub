"""Authentication dependencies.

The previous implementation relied on middleware that silently set
``request.state.user_id = None`` and let the request through. Protected
endpoints therefore returned a 500 (NOT NULL violation on ``owner_id``)
instead of a 401. These dependencies make the check explicit and return
the right status code.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.identifiers import to_uuid
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)
_INVALID_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user or raise 401."""
    if credentials is None or not credentials.credentials:
        raise _UNAUTHENTICATED

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise _INVALID_TOKEN

    user_id = to_uuid(payload.get("sub"))
    if user_id is None:
        raise _INVALID_TOKEN

    user = db.get(User, user_id)
    if user is None:
        raise _INVALID_TOKEN
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    request.state.user_id = str(user.id)
    return user


def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Resolve the authenticated user or raise 403 if they are not an admin."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
