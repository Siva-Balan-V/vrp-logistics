import time

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "vrp_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "vrp_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

IN_FLIGHT = Gauge(
    "vrp_http_requests_in_flight",
    "Current in-flight requests",
    ["method"],
)

SOLVER_DURATION = Histogram(
    "vrp_solver_duration_seconds",
    "VRP solver execution time",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0),
)

SOLVER_RESULT = Counter(
    "vrp_solver_results_total",
    "VRP solver results",
    ["status"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return Response(content=generate_latest(), media_type="text/plain")

        method = request.method
        path = request.url.path

        IN_FLIGHT.labels(method=method).inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = time.perf_counter() - start
            status = response.status_code if "response" in dir() else 500
            REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)
            IN_FLIGHT.labels(method=method).dec()
