"""Observability: JSON request logs + in-memory metrics + /admin/metrics
+ Prometheus text at /metrics.

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


def norm_path(path: str) -> str:
    """Bound cardinality: keep first two segments, collapse the rest to '*'
    (e.g. /admin/maps/udyam-register/steps -> /admin/maps/*)."""
    parts = [p for p in path.split("/") if p]
    if len(parts) <= 2:
        return "/" + "/".join(parts) if parts else "/"
    return "/" + "/".join(parts[:2]) + "/*"


def snapshot() -> dict:
    out = {}
    for route, s in _stats.items():
        avg = round(s["ms_total"] / s["hits"], 1) if s["hits"] else 0
        out[route] = {"hits": s["hits"], "errors": s["errors"], "avg_ms": avg}
    return out


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def prometheus() -> str:
    lines = [
        "# HELP civic_http_requests_total HTTP requests by normalized route.",
        "# TYPE civic_http_requests_total counter",
    ]
    for route, s in sorted(_stats.items()):
        label = f'route="{_esc(route)}"'
        lines.append(f"civic_http_requests_total{{{label}}} {s['hits']}")
    lines.append("# HELP civic_http_errors_total HTTP 5xx responses by route.")
    lines.append("# TYPE civic_http_errors_total counter")
    for route, s in sorted(_stats.items()):
        lines.append(f'civic_http_errors_total{{route="{_esc(route)}"}} {s["errors"]}')
    lines.append("# HELP civic_http_request_duration_ms_total Cumulative request time.")
    lines.append("# TYPE civic_http_request_duration_ms_total counter")
    for route, s in sorted(_stats.items()):
        lines.append(f'civic_http_request_duration_ms_total{{route="{_esc(route)}"}} {s["ms_total"]}')
    return "\n".join(lines) + "\n"


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
        route = norm_path(request.url.path)
        s = _stats[route]
        s["hits"] += 1
        s["ms_total"] += ms
        if status >= 500:
            s["errors"] += 1
        logger.info(json.dumps({"m": request.method, "p": request.url.path,
                                "s": status, "ms": ms}))
    return resp
