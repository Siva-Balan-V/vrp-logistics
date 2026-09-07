"""Tests for the Prometheus metrics endpoint and gauges."""

from app.middleware.metrics import REDIS_CONNECTED
from app.services import cache


def test_metrics_endpoint_exposes_expected_series():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "vrp_http_requests_total" in body
    assert "vrp_solver_duration_seconds_bucket" in body
    assert "vrp_solver_results_total" in body
    assert "vrp_http_requests_in_flight" in body
    assert "vrp_redis_connected" in body


def test_redis_connected_gauge_tracks_cache_state(monkeypatch):
    """REDIS_CONNECTED flips to 1/0 as is_redis_connected reports connectivity."""
    REDIS_CONNECTED.set(0)
    monkeypatch.setattr(cache, "_redis_client", None)
    assert cache.is_redis_connected() is False
    assert REDIS_CONNECTED._value.get() == 0.0
