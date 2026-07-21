import json

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None

from app.core.config import settings
from app.core.logger import logger

redis_client = None

try:
    if redis_lib and settings.REDIS_URL:
        redis_client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info("Redis connected")
    else:
        logger.warning("Redis not available - running without cache")
except Exception as e:
    logger.warning(f"Redis unavailable: {e}")
    redis_client = None


def cache_link(short_code: str, original_url: str, ttl: int = None) -> None:
    if not redis_client:
        return
    try:
        key = f"link:{short_code}"
        redis_client.setex(key, ttl or settings.REDIS_CACHE_TTL, original_url)
    except Exception:
        pass


def get_cached_link(short_code: str) -> str | None:
    if not redis_client:
        return None
    try:
        key = f"link:{short_code}"
        return redis_client.get(key)
    except Exception:
        return None


def invalidate_link_cache(short_code: str) -> None:
    if not redis_client:
        return
    try:
        redis_client.delete(f"link:{short_code}")
    except Exception:
        pass


def push_click_event(event_data: dict) -> None:
    if not redis_client:
        return
    try:
        redis_client.lpush("click_events", json.dumps(event_data))
    except Exception:
        pass


def check_rate_limit(identifier: str, limit: int = None, window: int = 60) -> bool:
    if not redis_client:
        return True
    try:
        key = f"rate_limit:{identifier}"
        current = redis_client.get(key)
        if current is None:
            redis_client.setex(key, window, 1)
            return True
        if int(current) >= (limit or settings.RATE_LIMIT_PER_MINUTE):
            return False
        redis_client.incr(key)
        return True
    except Exception:
        return True
