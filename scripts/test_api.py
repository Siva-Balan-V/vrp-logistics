#!/usr/bin/env python3
"""
Integration test – hits the live API with test datasets.
Usage:  python scripts/test_api.py [--url http://localhost:8000]
"""

import argparse, json, math, random, sys, time
import urllib.request, urllib.error


def gen_payload(n=30, seed=1, vehicles=5):
    random.seed(seed)
    dlat, dlon = 51.5074, -0.1278
    deliveries = []
    for i in range(1, n + 1):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0.005, 0.07)
        deliveries.append({
            "id": i, "demand": random.randint(1, 3),
            "lat": round(dlat + r * math.cos(angle), 6),
            "lon": round(dlon + r * math.sin(angle) * 1.4, 6),
            "label": f"Stop-{i:03d}",
        })
    return {
        "depot": {"id": 0, "lat": dlat, "lon": dlon, "demand": 0, "label": "London Depot"},
        "deliveries": deliveries,
        "vehicles": {"count": vehicles, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
        "routing_backend": "haversine",
    }


def post_json(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def run(base):
    passed = failed = 0
    print(f"\n{'='*52}\n  RouteForge API Integration Tests → {base}\n{'='*52}")

    def test(name, fn):
        nonlocal passed, failed
        print(f"\n▶ {name}")
        try:
            fn()
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    # 1. Health
    def t1():
        with urllib.request.urlopen(f"{base}/health", timeout=10) as r:
            h = json.loads(r.read())
        check(h["status"] == "ok", f"status={h['status']}")
        print(f"    version={h['version']}, backend={h['routing_backend']}")
    test("Health endpoint", t1)

    # 2. Optimize 30 locations
    job_id = None
    def t2():
        nonlocal job_id
        t0 = time.perf_counter()
        r = post_json(f"{base}/api/v1/optimize-routes", gen_payload(30))
        elapsed = time.perf_counter() - t0
        check(r["status"] == "success", f"status={r['status']}")
        check(r["vehicles_used"] > 0, "No vehicles used")
        check(r["assigned_count"] > 0, "No locations assigned")
        check(r["total_distance_km"] > 0, "Zero distance")
        job_id = r["job_id"]
        print(f"    {elapsed:.2f}s wall | solver={r['solver_time_seconds']}s")
        print(f"    assigned={r['assigned_count']}/30  vehicles={r['vehicles_used']}  dist={r['total_distance_km']} km")
    test("Optimize 30 locations (5 vehicles)", t2)

    # 3. Cached result
    def t3():
        check(job_id is not None, "No job_id from previous test")
        with urllib.request.urlopen(f"{base}/api/v1/routes/{job_id}", timeout=10) as r:
            cached = json.loads(r.read())
        check(cached["job_id"] == job_id, "job_id mismatch")
    test(f"GET cached result ({(job_id or '')[:12]}…)", t3)

    # 4. Validation – duplicate IDs
    def t4():
        bad = gen_payload(5)
        bad["deliveries"][1]["id"] = bad["deliveries"][0]["id"]
        req = urllib.request.Request(
            f"{base}/api/v1/optimize-routes",
            data=json.dumps(bad).encode(),
            headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=30)
            raise AssertionError("Expected 422, got 200")
        except urllib.error.HTTPError as e:
            check(e.code == 422, f"Expected 422, got {e.code}")
    test("Validation: duplicate IDs → 422", t4)

    # 5. 100 locations
    def t5():
        t0 = time.perf_counter()
        r = post_json(f"{base}/api/v1/optimize-routes", gen_payload(100, seed=77, vehicles=10))
        elapsed = time.perf_counter() - t0
        check(r["status"] == "success", f"status={r['status']}")
        print(f"    {elapsed:.2f}s wall | assigned={r['assigned_count']}/100 | unassigned={r['unassigned_count']}")
    test("Optimize 100 locations (10 vehicles)", t5)

    # Summary
    total = passed + failed
    status = "ALL PASSED ✓" if failed == 0 else f"{failed} FAILED ✗"
    print(f"\n{'='*52}")
    print(f"  {passed}/{total} tests passed — {status}")
    print(f"{'='*52}\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    run(parser.parse_args().url.rstrip("/"))
