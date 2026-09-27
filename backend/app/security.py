"""Security: rate limiter (memory or Redis store) + lockout helpers.

Store selection: REDIS_URL set -> shared Redis store (safe across multiple
gunicorn workers / instances); otherwise single-process memory store.
Same limits and key format either way. Redis runtime errors degrade to the
in-process MemoryStore (limits stay enforced, per-process precision) —
never a full bypass. Set RATE_LIMIT_FAIL_CLOSED=1 to reject requests
outright during a Redis outage instead.
"""
import os
import time
from collections import deque

from fastapi import HTTPException, Request

from .obs import warn
from fastapi.responses import JSONResponse

# prefix -> (max_hits, window_seconds)
LIMITS = {
    "/auth/login": (10, 300),
    "/auth/register": (10, 3600),
    "/auth/otp": (5, 600),
    "/admin": (60, 300),
    "default": (120, 60),
}

# probe endpoints must never be rate limited (LB/uptime checks)
EXEMPT_PATHS = ("/healthz", "/readyz", "/metrics")


def _prefix(path: str) -> str:
    for p in LIMITS:
        if p != "default" and path.startswith(p):
            return p
    return "default"


class MemoryStore:
    """Single-process sliding-window store (per IP + route prefix)."""

    def __init__(self):
        self._hits: dict[tuple[str, str], deque] = {}

    def allow(self, ip: str, prefix: str, max_hits: int, window: int) -> bool:
        now = time.time()
        key = (ip, prefix)
        q = self._hits.get(key)
        if q:
            while q and q[0] < now - window:
                q.popleft()
            if not q:
                del self._hits[key]
                q = None
        if q is None:
            q = deque()
        if len(q) >= max_hits:
            return False
        q.append(now)
        self._hits[key] = q
        return True


_store = None


def _get_store():
    global _store
    if _store is None:
        if os.environ.get("REDIS_URL", "").strip():
            try:
                from .security_redis import RedisStore, get_client
                client = get_client()
                _store = RedisStore(client, fallback=MemoryStore()) \
                    if client else MemoryStore()
            except Exception as e:
                warn("security", "redis store init failed, "
                     "using in-process memory store", error=e)
                _store = MemoryStore()
        else:
            _store = MemoryStore()
    return _store


def reset_store() -> None:
    """Drop the cached store (tests / REDIS_URL change)."""
    global _store
    _store = None


def check(request: Request):
    ip = (request.client.host if request.client else "?")
    prefix = _prefix(request.url.path)
    max_hits, window = LIMITS[prefix]
    if not _get_store().allow(ip, prefix, max_hits, window):
        raise HTTPException(429, f"rate limited: {max_hits}/{window}s on {prefix}")


async def rate_limit_middleware(request: Request, call_next):
    """App-wide enforcement (covers routes without explicit Depends).
    Returns JSON 429 instead of raising (middleware can't raise HTTPException)."""
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)
    ip = (request.client.host if request.client else "?")
    prefix = _prefix(request.url.path)
    max_hits, window = LIMITS[prefix]
    if not _get_store().allow(ip, prefix, max_hits, window):
        return JSONResponse(
            {"detail": f"rate limited: {max_hits}/{window}s"},
            429, headers={"Retry-After": str(window)})
    return await call_next(request)


# lockout policy
MAX_FAILS = 5
LOCK_SECONDS = 15 * 60
