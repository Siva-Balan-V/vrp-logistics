"""Tests for rate-limit middleware behavior."""

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware


def _make_app(optimize_limit: int, default_limit: int, trust_proxy_headers: bool = False):
    async def optimize(request):
        return PlainTextResponse("ok")

    async def status(request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/api/v1/optimize-routes", optimize, methods=["POST"]),
            Route("/api/v1/optimize-routes/{run_id}/status", status),
        ]
    )
    return RateLimitMiddleware(
        app, optimize_limit=optimize_limit, default_limit=default_limit, trust_proxy_headers=trust_proxy_headers
    )


class TestOptimizeLimitScope:
    def test_status_polling_does_not_consume_optimize_budget(self):
        app = _make_app(optimize_limit=2, default_limit=1000)
        with TestClient(app) as client:
            for _ in range(2):
                assert client.post("/api/v1/optimize-routes").status_code == 200
            assert client.post("/api/v1/optimize-routes").status_code == 429
            assert client.get("/api/v1/optimize-routes/abc/status").status_code == 200


class TestForwardedForHandling:
    def test_forwarded_for_ignored_by_default(self):
        app = _make_app(optimize_limit=100, default_limit=2)
        with TestClient(app) as client:
            for _ in range(2):
                resp = client.get("/api/v1/optimize-routes/abc/status")
                assert resp.status_code == 200
            resp = client.get(
                "/api/v1/optimize-routes/abc/status",
                headers={"X-Forwarded-For": "203.0.113.1"},
            )
            assert resp.status_code == 429

    def test_forwarded_for_trusted_when_enabled(self):
        app = _make_app(optimize_limit=100, default_limit=2, trust_proxy_headers=True)
        with TestClient(app) as client:
            for i in range(3):
                resp = client.get(
                    "/api/v1/optimize-routes/abc/status",
                    headers={"X-Forwarded-For": f"203.0.113.{i}"},
                )
                assert resp.status_code == 200
