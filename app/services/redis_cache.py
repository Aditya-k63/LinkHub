import json
import redis
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def cache_link(short_code: str, original_url: str, ttl: int = None) -> None:
    key = f"link:{short_code}"
    redis_client.setex(key, ttl or settings.REDIS_CACHE_TTL, original_url)


def get_cached_link(short_code: str) -> str | None:
    key = f"link:{short_code}"
    return redis_client.get(key)


def invalidate_link_cache(short_code: str) -> None:
    key = f"link:{short_code}"
    redis_client.delete(key)


def push_click_event(event_data: dict) -> None:
    redis_client.lpush("click_events", json.dumps(event_data))


def get_rate_limit_key(identifier: str) -> str:
    return f"rate_limit:{identifier}"


def check_rate_limit(identifier: str, limit: int = None, window: int = 60) -> bool:
    key = get_rate_limit_key(identifier)
    current = redis_client.get(key)

    if current is None:
        redis_client.setex(key, window, 1)
        return True

    if int(current) >= (limit or settings.RATE_LIMIT_PER_MINUTE):
        return False

    redis_client.incr(key)
    return True
