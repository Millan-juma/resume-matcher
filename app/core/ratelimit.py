import redis
from fastapi import HTTPException

from app.core.config import settings

r = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)


def limit(key: str, max_hits: int, window_seconds: int) -> None:
    try:
        k = f"rl:{key}"
        hits = r.incr(k)
        if hits == 1:
            r.expire(k, window_seconds)
    except redis.RedisError:
        return  # fail open
    if hits > max_hits:
        raise HTTPException(429, "Too many attempts. Try again later",
                            headers={"Retry-After": str(window_seconds)})
