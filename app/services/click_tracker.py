"""Click event construction.

Turns an inbound request into the payload that is persisted as a
:class:`~app.db.models.Click` row: client IP, user agent, referrer and the
parsed browser / OS / device.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request

from app.core.logger import logger

try:
    from ua_parser import user_agent_parser
except ImportError:  # pragma: no cover - ua-parser is a hard dependency
    user_agent_parser = None  # type: ignore[assignment]

#: Substrings that identify an automated client.
BOT_SIGNATURES = (
    "bot",
    "spider",
    "crawler",
    "crawling",
    "slurp",
    "bingpreview",
    "facebookexternalhit",
    "embedly",
    "quora link preview",
    "whatsapp",
    "telegrambot",
    "discordbot",
    "ahrefsbot",
    "semrushbot",
    "mj12bot",
    "dotbot",
    "petalbot",
)


def client_ip(request: Request) -> Optional[str]:
    """Return the caller's IP address.

    ``X-Forwarded-For`` holds a chain of proxies followed by the client,
    so the first entry is the original caller.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client and request.client.host:
        return request.client.host[:45]
    return None


def parse_user_agent(user_agent: Optional[str]) -> dict[str, Optional[str]]:
    """Break a user-agent string into browser / OS / device."""
    if not user_agent or user_agent_parser is None:
        return {"browser": None, "os": None, "device_type": None}

    try:
        parsed = user_agent_parser.Parse(user_agent)
        browser = parsed["user_agent"]["family"]
        os_name = parsed["os"]["family"]
        device = parsed["device"]["family"]
        return {
            "browser": _normalise(browser),
            "os": _normalise(os_name),
            "device_type": _normalise(device),
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not parse user agent: %s", exc)
        return {"browser": None, "os": None, "device_type": None}


def _normalise(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() in {"other", "unknown"}:
        return None
    return cleaned[:50]


def is_bot(user_agent: Optional[str]) -> bool:
    """Return True when the user agent looks automated."""
    if not user_agent:
        return False
    lowered = user_agent.lower()
    return any(signature in lowered for signature in BOT_SIGNATURES)


def build_click_event(request: Request, link_id: str, short_code: str) -> dict[str, Any]:
    """Build the payload describing a single click."""
    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer") or request.headers.get("referrer")

    parsed = parse_user_agent(user_agent)

    return {
        "link_id": link_id,
        "short_code": short_code,
        "ip_address": client_ip(request),
        "user_agent": user_agent,
        "referrer": referrer,
        "browser": parsed["browser"],
        "os": parsed["os"],
        "device_type": parsed["device_type"],
        "is_bot": is_bot(user_agent),
    }
