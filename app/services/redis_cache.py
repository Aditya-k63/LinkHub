"""Redis helpers: link caching, the click queue and rate limiting.

Redis is optional. When it is unavailable the application keeps working -
it simply loses caching and falls back to an in-process rate limiter, so a
Redis outage degrades performance instead of taking the API down.
"""

from __future__ import annotations

import contextlib
import threading
import time
from typing import Any

from app.core.config import settings
from app.core.logger import logger

try:
    import redis as redis_lib
except ImportError:  # pragma: no cover - redis is a hard dependency
    redis_lib = None  # type: ignore[assignment]

redis_client: Any | None = None

if redis_lib is not None and settings.REDIS_URL:
    try:
        redis_client = redis_lib.from_url(
            settings.REDIS_URL, decode_responses=True, socket_connect_timeout=5
        )
        redis_client.ping()
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning("Redis unavailable, continuing without cache: %s", exc)
        redis_client = None
else:
    logger.warning("REDIS_URL is not set, running without cache or shared rate limits")

# Atomic counter: increment, and only set the expiry on the first hit.
# A plain GET-then-INCR pair loses increments under concurrency.
_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""

_rate_limit_script = None
if redis_client is not None:
    try:
        _rate_limit_script = redis_client.register_script(_RATE_LIMIT_SCRIPT)
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not register rate limit script: %s", exc)


# --------------------------------------------------------------------------
# In-process fallback (used when Redis is unavailable)
# --------------------------------------------------------------------------

_local_lock = threading.Lock()
_local_buckets: dict[str, tuple[float, int]] = {}


def _local_rate_limit(key: str, limit: int, window: int) -> bool:
    """Fixed-window counter kept in this process' memory."""
    now = time.monotonic()
    with _local_lock:
        window_start, count = _local_buckets.get(key, (now, 0))
        if now - window_start >= window:
            window_start, count = now, 0
        count += 1
        _local_buckets[key] = (window_start, count)
        # Opportunistic cleanup so the dict cannot grow without bound.
        if len(_local_buckets) > 10_000:
            cutoff = now - window
            for stale in [k for k, (ws, _) in _local_buckets.items() if ws < cutoff]:
                _local_buckets.pop(stale, None)
        return count <= limit


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------


def redis_healthy() -> bool:
    """Return True when Redis answers a PING."""
    if redis_client is None:
        return False
    try:
        return bool(redis_client.ping())
    except Exception:
        return False


# --------------------------------------------------------------------------
# Link cache (cache-aside)
# --------------------------------------------------------------------------


def cache_link(short_code: str, original_url: str, ttl: int | None = None) -> None:
    """Cache the destination of a short code."""
    if redis_client is None:
        return
    try:
        redis_client.setex(f"link:{short_code}", ttl or settings.REDIS_CACHE_TTL, original_url)
    except Exception as exc:
        logger.warning("cache_link failed for %s: %s", short_code, exc)


def get_cached_link(short_code: str) -> str | None:
    """Return the cached destination for ``short_code`` if there is one."""
    if redis_client is None:
        return None
    try:
        return redis_client.get(f"link:{short_code}")
    except Exception as exc:
        logger.warning("get_cached_link failed for %s: %s", short_code, exc)
        return None


def invalidate_link_cache(short_code: str) -> None:
    """Drop the cached destination for ``short_code``."""
    if redis_client is None:
        return
    try:
        redis_client.delete(f"link:{short_code}")
    except Exception as exc:
        logger.warning("invalidate_link_cache failed for %s: %s", short_code, exc)


def cache_link_record(short_code: str, payload: dict) -> None:
    """Cache the full link metadata used by the redirect hot path."""
    if redis_client is None:
        return
    try:
        import json

        redis_client.setex(f"link:{short_code}", settings.REDIS_CACHE_TTL, json.dumps(payload))
    except Exception as exc:
        logger.warning("cache_link_record failed for %s: %s", short_code, exc)


def get_cached_link_record(short_code: str) -> dict | None:
    """Return the cached link metadata for ``short_code``, if present."""
    if redis_client is None:
        return None
    try:
        import json

        raw = redis_client.get(f"link:{short_code}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("get_cached_link_record failed for %s: %s", short_code, exc)
        return None


# --------------------------------------------------------------------------
# Click queue
# --------------------------------------------------------------------------


def push_click_event(event_data: dict) -> None:
    """Enqueue a click event for a worker to persist."""
    if redis_client is None:
        return
    try:
        import json

        redis_client.lpush("click_events", json.dumps(event_data))
    except Exception as exc:
        logger.warning("push_click_event failed: %s", exc)


def pop_click_event(timeout: int = 1) -> dict | None:
    """Pop the oldest queued click event, if any."""
    if redis_client is None:
        return None
    try:
        import json

        raw = redis_client.brpop("click_events", timeout=timeout)
        if not raw:
            return None
        return json.loads(raw[1])
    except Exception as exc:
        logger.warning("pop_click_event failed: %s", exc)
        return None


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def check_rate_limit(
    identifier: str,
    limit: int | None = None,
    window: int = 60,
) -> bool:
    """Return True when the request is allowed.

    Uses an atomic Redis counter when available and an in-process fixed
    window otherwise.
    """
    effective_limit = limit or settings.RATE_LIMIT_PER_MINUTE
    key = f"rate_limit:{identifier}"

    if redis_client is not None and _rate_limit_script is not None:
        try:
            current = int(_rate_limit_script(keys=[key], args=[window]))
            return current <= effective_limit
        except Exception as exc:
            logger.warning("Redis rate limit failed, using local limiter: %s", exc)

    return _local_rate_limit(key, effective_limit, window)


def reset_rate_limit(identifier: str) -> None:
    """Clear the counter for ``identifier`` (used by the test-suite)."""
    if redis_client is not None:
        with contextlib.suppress(Exception):
            redis_client.delete(f"rate_limit:{identifier}")
    with _local_lock:
        _local_buckets.pop(f"rate_limit:{identifier}", None)
