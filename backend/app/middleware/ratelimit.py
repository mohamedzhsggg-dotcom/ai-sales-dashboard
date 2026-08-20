"""Rate limiting middleware.

Token-bucket per user (and a tighter limit for /auth endpoints). Uses Redis when
available and transparently falls back to an in-process window when Redis is
unreachable, so the API never hard-fails on Redis being down.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings

settings = get_settings()

# In-memory fallback: {key: [timestamps]}
_memory_buckets: dict[str, list[float]] = {}

try:
    import redis as _redis

    _client = _redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
except Exception:  # pragma: no cover - redis import failure
    _client = None


def _rate_limit_key(request) -> str:
    user = getattr(request.state, "user_id", None)
    if user:
        return f"rl:u:{user}"
    ip = request.client.host if request.client else "unknown"
    return f"rl:ip:{ip}"


def _allow_redis(key: str, limit: int, window: int) -> bool:
    try:
        pipe = _client.pipeline()
        now_ms = int(time.time() * 1000)
        pipe.zremrangebyscore(key, 0, now_ms - window * 1000)
        pipe.zadd(key, {str(now_ms): now_ms})
        pipe.zcard(key)
        pipe.expire(key, window)
        count = pipe.execute()[-2]
        return int(count) <= limit
    except Exception:
        return True  # Redis hiccup: allow, never block the app


def _allow_memory(key: str, limit: int, window: int) -> bool:
    now = time.time()
    bucket = _memory_buckets.setdefault(key, [])
    cutoff = now - window
    _memory_buckets[key] = [t for t in bucket if t > cutoff]
    if len(_memory_buckets[key]) >= limit:
        return False
    _memory_buckets[key].append(now)
    return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        key = _rate_limit_key(request)
        path = request.url.path
        is_auth = path.rstrip("/").endswith("/auth/login") or path.rstrip("/").endswith("/auth/setup")
        limit = settings.RATE_LIMIT_AUTH_PER_MINUTE if is_auth else settings.RATE_LIMIT_PER_MINUTE

        allowed = _allow_redis(key, limit, 60) if _client else _allow_memory(key, limit, 60)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "too_many_requests",
                        "message": "Rate limit exceeded, slow down",
                        "detail": None,
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
                headers={"Retry-After": "60"},
            )

        return await call_next(request)