import hashlib
import hmac
from functools import lru_cache

from redis import Redis

from app.config import get_settings

COUNTER = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        socket_timeout=2,
        socket_connect_timeout=2,
        max_connections=20,
        decode_responses=True,
    )


def consume(identity: str, limit: int, seconds: int = 60) -> tuple[bool, int]:
    settings = get_settings()
    key = hmac.new(
        settings.rate_limit_secret.encode(), identity.encode(), hashlib.sha256
    ).hexdigest()
    count, ttl = get_redis().eval(COUNTER, 1, f"{settings.rate_namespace}:{key}", seconds)
    return count <= limit, max(1, ttl)
