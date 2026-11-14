"""QR code endpoint.

Serves the QR code as a PNG image so the frontend can point an ``<img>`` at
it directly instead of embedding a base64 blob in every JSON response.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.qr_service import generate_qr_png
from app.services.shortener import get_link_by_code

router = APIRouter(prefix="/api/qr", tags=["qr"])


@router.get("/{short_code}.png")
def qr_code(
    short_code: str,
    size: int = Query(default=10, ge=2, le=40),
    db: Session = Depends(get_db),
) -> Response:
    """Return the QR code for a short code as a PNG image."""
    link = get_link_by_code(db, short_code, include_inactive=True)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    short_url = f"{settings.public_base_url}/{link.short_code}"
    png = generate_qr_png(short_url, box_size=size)

    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
