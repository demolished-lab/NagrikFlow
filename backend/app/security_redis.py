"""Redis-backed shared rate-limit store for multi-worker deployments.

Set REDIS_URL=redis://host:6379/0 and the app switches from the in-process
memory store to this one automatically (see security._get_store). Keys use
the same (ip, prefix) semantics as the memory store so limits match exactly.
Connection failures are surfaced to _get_store which falls back to memory.
"""
import os
import time

_client = None
_client_failed = False


def get_client():
    global _client, _client_failed
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    if _client is not None:
        return _client
    if _client_failed:
        return None
    try:
        import redis
        _client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        _client.ping()
        return _client
    except Exception:
        _client_failed = True
        return None


def reset() -> None:
    """Drop the cached client (tests / REDIS_URL change)."""
    global _client, _client_failed
    _client = None
    _client_failed = False


class RedisStore:
    """Sliding-window limiter shared by all workers. Fail-open on Redis errors
    (availability over strictness; per-process memory limiting still applies
    only when Redis is entirely unconfigured)."""

    def __init__(self, client):
        self.r = client

    def allow(self, ip: str, prefix: str, max_hits: int, window: int) -> bool:
        key = f"rate:{ip}:{prefix}"
        now = time.time()
        cutoff = now - window
        try:
            rows = self.r.lrange(key, 0, -1)
            timestamps = [float(x.decode() if isinstance(x, bytes) else x)
                          for x in rows]
            timestamps = [x for x in timestamps if x > cutoff]
            if len(timestamps) >= max_hits:
                return False
            pipe = self.r.pipeline()
            pipe.lpush(key, now)
            pipe.expire(key, window + 1)
            pipe.execute()
            return True
        except Exception:
            return True  # Redis down -> fail open (memory limiter is bypassed;
            # alert on Redis health via /readyz instead)
