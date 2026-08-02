"""
Simple in-memory sliding window rate limiter.

Per-IP-per-path tracking with periodic cleanup to prevent unbounded memory growth.
Returns standard rate-limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, Retry-After).
"""

from __future__ import annotations

import math
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        optimize_limit: int = 30,
        default_limit: int = 120,
        window_seconds: int = 60,
        trust_proxy_headers: bool = False,
    ):
        super().__init__(app)
        self.optimize_limit = optimize_limit
        self.default_limit = default_limit
        self.window = window_seconds
        self.trust_proxy_headers = trust_proxy_headers
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time.monotonic()

    def _get_client_ip(self, request: Request) -> str:
        if self.trust_proxy_headers:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_stale(self) -> None:
        now = time.monotonic()
        cutoff = now - self.window
        stale_keys = [k for k, v in self._hits.items() if not v or v[-1] < cutoff]
        for k in stale_keys:
            del self._hits[k]

    def _check_limit(self, client_ip: str, path: str) -> tuple[int, int, float]:
        now = time.monotonic()
        cutoff = now - self.window

        limit = self.optimize_limit if path == "/api/v1/optimize-routes" else self.default_limit

        key = f"{client_ip}:{path}"
        hits = self._hits[key]
        active = [t for t in hits if t > cutoff]
        self._hits[key] = active

        remaining = max(0, limit - len(active))
        retry_after = 0.0
        if len(active) >= limit:
            retry_after = max(0.0, self.window - (now - active[0]))

        if len(active) < limit:
            self._hits[key].append(now)

        return limit, remaining, retry_after

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health") or request.url.path == "/":
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        # Periodic cleanup every 30 seconds
        now = time.monotonic()
        if now - self._last_cleanup > 30:
            self._cleanup_stale()
            self._last_cleanup = now

        limit, remaining, retry_after = self._check_limit(client_ip, request.url.path)

        if remaining == 0:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(math.ceil(retry_after)),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
