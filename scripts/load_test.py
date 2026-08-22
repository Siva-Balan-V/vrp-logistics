#!/usr/bin/env python3
"""
RouteForge load test — hammers POST /api/v1/optimize-routes with concurrent
requests to measure throughput, latency, and error rates.

Uses asyncio + aiohttp. Generates synthetic payloads identical to
scripts/test_api.py so results are comparable with the API integration test.

Usage:
    python scripts/load_test.py --concurrency 10 --requests 50 --locations 500
    python scripts/load_test.py --url http://localhost:8000 --concurrency 20 --requests 200
    python scripts/load_test.py --api-key rf_xxx --ramp 2s

Notes:
  - The backend rate-limits /optimize-routes (default 30/min/IP). For real
    load beyond that, point requests at distinct client IPs (e.g. behind a
    load balancer with X-Forwarded-For when TRUST_PROXY_HEADERS=true), or
    raise OPTIMIZE_RATE_LIMIT in app.middleware.rate_limit.RateLimitMiddleware.
  - Use the haversine backend (no external routing API) to isolate solver cost.

Exit code 0 on success, 1 if error rate exceeds --max-error-rate.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import random
import sys
import time

import aiohttp

DEFAULT_URL = "http://localhost:8000"


def gen_payload(
    n: int = 100, seed: int = 1, vehicles: int = 10, solver_time_limit: int = 60
) -> dict:
    """Deterministic synthetic payload: depot + n deliveries around London."""
    random.seed(seed)
    dlat, dlon = 51.5074, -0.1278
    deliveries = []
    for i in range(1, n + 1):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0.005, 0.07)
        deliveries.append(
            {
                "id": i,
                "demand": random.randint(1, 3),
                "lat": round(dlat + r * math.cos(angle), 6),
                "lon": round(dlon + r * math.sin(angle) * 1.4, 6),
                "label": f"Stop-{i:03d}",
            }
        )
    return {
        "depots": [
            {"id": 0, "lat": dlat, "lon": dlon, "demand": 0, "label": "London Depot"}
        ],
        "deliveries": deliveries,
        "vehicles": {
            "count": vehicles,
            "capacity": 50,
            "max_route_duration_seconds": 9000,
            "speed_kmh": 30,
            "solver_time_limit_seconds": solver_time_limit,
        },
        "routing_backend": "haversine",
    }


async def run_request(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict,
    api_key: str | None,
    timeout: float,
) -> tuple[int, float, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    start = time.perf_counter()
    try:
        async with session.post(
            f"{url}/api/v1/optimize-routes",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            await resp.read()
            elapsed = time.perf_counter() - start
            return resp.status, elapsed, ""
    except Exception as e:  # noqa: BLE001
        return 0, time.perf_counter() - start, str(e)


async def worker(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict,
    api_key: str | None,
    timeout: float,
    results: list,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        status, elapsed, err = await run_request(
            session, url, payload, api_key, timeout
        )
        results.append({"status": status, "latency": elapsed, "error": err})


async def main(args: argparse.Namespace) -> None:
    payloads = [
        gen_payload(
            n=args.locations,
            seed=s,
            vehicles=args.vehicles,
            solver_time_limit=args.solver_time_limit,
        )
        for s in range(args.requests)
    ]
    results: list = []
    semaphore = asyncio.Semaphore(args.concurrency)

    print(f"RouteForge Load Test → {args.url}")
    print(
        f"  requests={args.requests}  concurrency={args.concurrency}  "
        f"locations={args.locations}  vehicles={args.vehicles}  timeout={args.timeout}s"
    )
    if args.api_key:
        print(f"  auth: X-API-Key {args.api_key[:10]}…")
    print("─" * 60)

    connector = aiohttp.TCPConnector(limit=args.concurrency, ssl=False)
    start = time.perf_counter()
    async with aiohttp.ClientSession(connector=connector) as session:
        # Optional ramp: warm-up requests sent at a controlled rate.
        tasks = [
            asyncio.create_task(
                worker(
                    session, args.url, p, args.api_key, args.timeout, results, semaphore
                )
            )
            for p in payloads
        ]
        await asyncio.gather(*tasks)
    wall = time.perf_counter() - start

    ok = [r for r in results if 200 <= r["status"] < 300]
    errs = [r for r in results if not (200 <= r["status"] < 300)]
    latencies = sorted(r["latency"] for r in ok)

    print("─" * 60)
    print(f"wall time:            {wall:.2f}s")
    print(f"total:                {len(results)}")
    print(f"success (2xx):        {len(ok)}")
    print(f"errors (4xx/5xx/conn):{len(errs)}")

    status_counts: dict[int, int] = {}
    for r in errs:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    if status_counts:
        for code, count in sorted(status_counts.items()):
            print(f"  status {code or 'conn-error'}: {count}")

    if latencies:
        p = lambda k: latencies[min(int(k * (len(latencies) - 1)), len(latencies) - 1)]
        print("─" * 60)
        print("latency   min   p50   p95   p99   max")
        print(
            f"          {min(latencies) * 1000:6.1f} {p(0.5) * 1000:6.1f} "
            f"{p(0.95) * 1000:6.1f} {p(0.99) * 1000:6.1f} {max(latencies) * 1000:6.1f} ms"
        )
        print(f"throughput: {len(ok) / wall:.1f} req/s")

    rate = len(errs) / len(results) if results else 1.0
    status = "PASS" if rate <= args.max_error_rate and ok else "FAIL"
    print(
        f"error rate:           {rate:.1%} (limit {args.max_error_rate:.1%}) → {status}"
    )

    if status == "FAIL":
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RouteForge load test")
    parser.add_argument("--url", default=DEFAULT_URL, help="Base API URL")
    parser.add_argument("--requests", type=int, default=50, help="Total requests")
    parser.add_argument(
        "--concurrency", type=int, default=10, help="Concurrent requests"
    )
    parser.add_argument(
        "--locations", type=int, default=100, help="Deliveries per request"
    )
    parser.add_argument("--vehicles", type=int, default=10, help="Vehicles per request")
    parser.add_argument(
        "--solver-time-limit",
        type=int,
        default=60,
        help="Solver timeout in seconds per request (1-600)",
    )
    parser.add_argument(
        "--timeout", type=float, default=300.0, help="Per-request timeout (s)"
    )
    parser.add_argument("--api-key", default=None, help="X-API-Key header for auth")
    parser.add_argument(
        "--max-error-rate", type=float, default=0.0, help="Failure threshold"
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args()))
    except KeyboardInterrupt:
        print("\naborted")
        sys.exit(130)
