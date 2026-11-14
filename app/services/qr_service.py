"""QR code generation."""

from __future__ import annotations

import base64
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def _build(url: str, box_size: int) -> qrcode.main.QRCode:
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr


def generate_qr_png(url: str, box_size: int = 10) -> bytes:
    """Return the QR code for ``url`` as PNG bytes."""
    qr = _build(url, box_size)
    image = qr.make_image(fill_color="#1a1a2e", back_color="white")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr_code(url: str) -> str:
    """Return the QR code for ``url`` as a base64 data URI."""
    png = generate_qr_png(url)
    encoded = base64.b64encode(png).decode()
    return f"data:image/png;base64,{encoded}"
