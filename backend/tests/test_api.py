"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_request():
    return {
        "depot": {"id": 0, "lat": 51.5074, "lon": -0.1278, "demand": 0, "label": "Depot"},
        "deliveries": [
            {"id": i, "lat": 51.51 + i * 0.001, "lon": -0.07 + i * 0.001, "demand": 1, "label": f"Stop {i}"}
            for i in range(1, 6)
        ],
        "vehicles": {"count": 3, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
    }


def test_health_endpoint(client):
    """Health endpoint should return ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "routing_backend" in data
    assert "redis_connected" in data


def test_root_endpoint(client):
    """Root endpoint should return API info."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "docs" in data


def test_optimize_routes_success(client, sample_request):
    """Optimization should succeed with valid input."""
    resp = client.post("/api/v1/optimize-routes", json=sample_request)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["total_locations"] == 5
    assert data["vehicles_used"] >= 1
    assert "job_id" in data
    assert "solver_time_seconds" in data


def test_optimize_routes_duplicate_ids(client):
    """Duplicate delivery IDs should return 422."""
    req = {
        "depot": {"id": 0, "lat": 51.5074, "lon": -0.1278, "demand": 0},
        "deliveries": [
            {"id": 1, "lat": 51.51, "lon": -0.07, "demand": 1},
            {"id": 1, "lat": 51.52, "lon": -0.08, "demand": 1},
        ],
        "vehicles": {"count": 2, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
    }
    resp = client.post("/api/v1/optimize-routes", json=req)
    assert resp.status_code == 422


def test_optimize_routes_depot_id_conflict(client):
    """Depot ID conflicting with delivery ID should return 422."""
    req = {
        "depot": {"id": 1, "lat": 51.5074, "lon": -0.1278, "demand": 0},
        "deliveries": [
            {"id": 1, "lat": 51.51, "lon": -0.07, "demand": 1},
        ],
        "vehicles": {"count": 2, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
    }
    resp = client.post("/api/v1/optimize-routes", json=req)
    assert resp.status_code == 422


def test_get_routes_not_found(client):
    """Getting non-existent job should return 404."""
    resp = client.get("/api/v1/routes/nonexistent-id")
    assert resp.status_code == 404


def test_get_routes_after_optimize(client, sample_request):
    """Should retrieve cached result after optimization."""
    optimize_resp = client.post("/api/v1/optimize-routes", json=sample_request)
    job_id = optimize_resp.json()["job_id"]

    resp = client.get(f"/api/v1/routes/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id


def test_list_routes(client):
    """List routes should return job summaries."""
    resp = client.get("/api/v1/routes")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "jobs" in data
