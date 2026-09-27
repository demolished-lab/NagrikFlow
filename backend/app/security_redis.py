"""Optional Redis-backed rate limiter.
Use when deploying with multiple workers behind a load balancer.

Install: pip install redis
Set: REDIS_URL=redis://localhost:6379/0
"""
import os
from collections import deque
from datetime import datetime, timezone

try:
    import redis as _redis
    _REDIS = _redis.from_url(os.environ.get("REDIS_URL", ""))
except ImportError:
    _REDIS = None


def redis_check(ip: str, prefix: str, max_hits: int, window: int) -> bool:
    """Return True if allowed, False if rate limited. Redis-backed."""
    if not _REDIS or not os.environ.get("REDIS_URL"):
        return True  # Fallback: allow if Redis not configured
    key = f"rate:{ip}:{prefix}"
    now = datetime.now(timezone.utc).timestamp()
    pipe = _REDIS.pipeline()
    pipe.lpush(key, now)
    pipe.expire(key, window + 1)
    pipe.lrange(key, 0, -1)
    results = pipe.execute()
    timestamps = results[2]
    # Prune old entries
    cutoff = now - window
    while timestamps and float(timestamps[-1]) < cutoff:
        timestamps.pop()
    if len(timestamps) > max_hits:
        return False
    return True


def redis_limit_middleware(request, call_next):
    """FastAPI middleware using Redis for distributed rate limiting."""
    from fastapi import HTTPException
    ip = request.client.host if request.client else "?"
    prefix = request.url.path.split("/")[1] if request.url.path.startswith("/") else "root"
    # Use same limits as security.py
    LIMITS = {"/auth/login": (10, 300), "/auth/register": (10, 3600),
              "/auth/otp": (5, 600), "/admin": (60, 300), "default": (120, 60)}
    max_hits, window = LIMITS.get(prefix, LIMITS["default"])
    if not redis_check(ip, prefix, max_hits, window):
        raise HTTPException(429, f"rate limited: {max_hits}/{window}s on {prefix}")
    return call_next(request)
