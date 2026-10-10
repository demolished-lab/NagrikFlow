#!/usr/bin/env python3
"""Concurrent latency smoke test for the NagrikFlow performance dashboard API.

Examples:
  python3 tools/stress_performance.py --url http://127.0.0.1:8000/readyz
  python3 tools/stress_performance.py --url http://127.0.0.1:8000/admin/metrics --bearer "$TOKEN" --requests 200 --concurrency 25
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def one(url: str, timeout: float, bearer: str) -> dict:
    started = time.perf_counter()
    request = Request(url, headers={"Accept": "application/json", **({"Authorization": f"Bearer {bearer}"} if bearer else {})})
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
            return {"ok": 200 <= response.status < 400, "status": response.status, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    except HTTPError as error:
        return {"ok": False, "status": error.code, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    except (URLError, TimeoutError, OSError) as error:
        return {"ok": False, "status": 0, "error": type(error).__name__, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int(len(values) * fraction + .999) - 1))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stress-test a NagrikFlow JSON API endpoint concurrently.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/readyz")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--bearer", default="")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")

    started = time.perf_counter()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(one, args.url, args.timeout, args.bearer) for _ in range(args.requests)]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = time.perf_counter() - started
    latencies = [item["latency_ms"] for item in results]
    errors = sum(1 for item in results if not item["ok"])
    report = {
        "url": args.url,
        "requests": len(results),
        "concurrency": args.concurrency,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_per_second": round(len(results) / elapsed, 2) if elapsed else 0,
        "errors": errors,
        "error_rate_percent": round(errors / len(results) * 100, 2),
        "status_counts": {str(status): sum(1 for item in results if item["status"] == status) for status in sorted({item["status"] for item in results})},
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0,
            "avg": round(statistics.mean(latencies), 2) if latencies else 0,
            "p50": round(percentile(latencies, .50), 2),
            "p95": round(percentile(latencies, .95), 2),
            "max": round(max(latencies), 2) if latencies else 0,
        },
    }
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
