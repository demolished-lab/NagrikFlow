"""Security: stdlib rate limiter + lockout helpers. No new dependencies.

Rate limits are per (client IP, route-prefix). Single-process memory store —
correct for current SQLite dev deploy; move to Redis when multi-worker.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# prefix -> (max_hits, window_seconds)
LIMITS = {
    "/auth/login": (10, 300),
    "/auth/register": (10, 3600),
    "/auth/otp": (5, 600),
    "/admin": (60, 300),
    "default": (120, 60),
}

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def _prefix(path: str) -> str:
    for p in LIMITS:
        if p != "default" and path.startswith(p):
            return p
    return "default"


def check(request: Request):
    ip = (request.client.host if request.client else "?")
    key = (ip, _prefix(request.url.path))
    max_hits, window = LIMITS[key[1]]
    now = time.time()
    q = _hits[key]
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= max_hits:
        raise HTTPException(429, f"rate limited: {max_hits}/{window}s on {key[1]}")
    q.append(now)


async def rate_limit_middleware(request: Request, call_next):
    """App-wide enforcement (covers routes without explicit Depends).
    Returns JSON 429 instead of raising (middleware can't raise HTTPException)."""
    from fastapi.responses import JSONResponse
    ip = (request.client.host if request.client else "?")
    key = (ip, _prefix(request.url.path))
    max_hits, window = LIMITS[key[1]]
    now = time.time()
    q = _hits[key]
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= max_hits:
        return JSONResponse({"detail": f"rate limited: {max_hits}/{window}s"}, 429)
    q.append(now)
    return await call_next(request)


# lockout policy
MAX_FAILS = 5
LOCK_SECONDS = 15 * 60
