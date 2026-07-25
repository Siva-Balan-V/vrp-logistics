"""
Simple in-memory sliding window rate limiter.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, optimize_limit: int = 30, default_limit: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.optimize_limit = optimize_limit
        self.default_limit = default_limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, client_ip: str, path: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window

        limit = self.optimize_limit if path.startswith("/api/v1/optimize-routes") else self.default_limit

        key = f"{client_ip}:{path}"
        hits = self._hits[key]
        self._hits[key] = [t for t in hits if t > cutoff]

        if len(self._hits[key]) >= limit:
            return True

        self._hits[key].append(now)
        return False

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health") or request.url.path == "/":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        if self._is_rate_limited(client_ip, request.url.path):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )
        return await call_next(request)
