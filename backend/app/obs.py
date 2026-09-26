"""Observability: JSON request logs + in-memory metrics + /admin/metrics.

Zero new deps. Counters reset on restart (ship to Grafana/Loki later via
the JSON log stream). Never logs tokens, passwords, OTP codes, or doc numbers:
request bodies are never logged, only method/path/status/ms.
"""
import json
import logging
import os
import time
from collections import defaultdict

logger = logging.getLogger("civic")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(h)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_stats: dict[str, dict] = defaultdict(lambda: {"hits": 0, "errors": 0, "ms_total": 0})


def snapshot() -> dict:
    out = {}
    for route, s in _stats.items():
        avg = round(s["ms_total"] / s["hits"], 1) if s["hits"] else 0
        out[route] = {"hits": s["hits"], "errors": s["errors"], "avg_ms": avg}
    return out


async def obs_middleware(request, call_next):
    start = time.time()
    try:
        resp = await call_next(request)
        status = resp.status_code
    except Exception:
        status = 500
        raise
    finally:
        ms = round((time.time() - start) * 1000, 1)
        route = request.url.path
        s = _stats[route]
        s["hits"] += 1
        s["ms_total"] += ms
        if status >= 500:
            s["errors"] += 1
        logger.info(json.dumps({"m": request.method, "p": route,
                                "s": status, "ms": ms}))
    return resp
