"""Unit tests for every API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_principal, require_principal
from app.main import create_app
from app.models.schemas import OptimizeResponse, VehicleRoute
from app.routes.optimization import _DEFAULT_COMPANY_ID


def _make_fake_response(job_id: str = "test-id") -> OptimizeResponse:
    return OptimizeResponse(
        job_id=job_id,
        status="success",
        solver_time_seconds=0.123,
        total_locations=2,
        assigned_count=2,
        unassigned_count=0,
        vehicles_used=1,
        total_distance_km=45.0,
        total_time_minutes=90.0,
        vehicles=[
            VehicleRoute(
                vehicle_id=1,
                route=[0, 1, 2, 0],
                route_labels=["Depot", "Stop 1", "Stop 2", "Depot"],
                distance_km=45.0,
                time_minutes=90.0,
                packages_delivered=2,
            ),
        ],
        unassigned=[],
        unassigned_labels=[],
        matrix_source="haversine",
    )


@pytest.fixture
def client():
    app = create_app()
    mock_user = MagicMock()
    mock_user.company_id = "00000000-0000-0000-0000-000000000001"
    app.dependency_overrides[require_principal] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clear_cache():
    from app.services.cache import _job_cache, _lru

    _job_cache.clear()
    _lru.clear()
    yield


@pytest.fixture(autouse=True)
def mock_solver(request):
    """Mock the VRP solver for all tests except those marked realsolver."""
    if "realsolver" in request.keywords:
        yield
        return
    with patch("app.routes.optimization.run_optimization_sync") as mock:

        def fake_solve(req, run_id=None, company_id=None):
            from app.services import cache

            jid = req.job_id or "test-id"
            resp = _make_fake_response(job_id=jid)
            cache.set_job(company_id, jid, resp.model_dump())
            return resp

        mock.side_effect = fake_solve
        yield


@pytest.fixture
def sample_request():
    return {
        "depot": {"id": 0, "lat": 51.5074, "lon": -0.1278, "demand": 0, "label": "Depot"},
        "deliveries": [
            {"id": 1, "lat": 51.51, "lon": -0.07, "demand": 1, "label": "Stop 1"},
            {"id": 2, "lat": 51.52, "lon": -0.08, "demand": 1, "label": "Stop 2"},
        ],
        "vehicles": {"count": 3, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
    }


# ─────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_structure(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "routing_backend" in data
        assert "redis_connected" in data

    def test_health_version_matches_config(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert data["version"] == "1.0.0"

    def test_health_routing_backend_default(self, client):
        resp = client.get("/health")
        assert resp.json()["routing_backend"] == "haversine"

    def test_health_redis_disconnected_by_default(self, client):
        resp = client.get("/health")
        assert resp.json()["redis_connected"] is False


# ─────────────────────────────────────────────
# GET /
# ─────────────────────────────────────────────


class TestRootEndpoint:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_has_message(self, client):
        resp = client.get("/")
        data = resp.json()
        assert "message" in data
        assert "VRP" in data["message"]

    def test_root_has_docs_link(self, client):
        resp = client.get("/")
        data = resp.json()
        assert data["docs"] == "/docs"


# ─────────────────────────────────────────────
# POST /api/v1/optimize-routes
# ─────────────────────────────────────────────


class TestOptimizeRoutes:
    def test_success_returns_200(self, client, sample_request):
        resp = client.post("/api/v1/optimize-routes", json=sample_request)
        assert resp.status_code == 200

    def test_success_response_structure(self, client, sample_request):
        resp = client.post("/api/v1/optimize-routes", json=sample_request)
        data = resp.json()
        assert data["status"] == "success"
        assert "job_id" in data
        assert "solver_time_seconds" in data
        assert "total_locations" in data
        assert "assigned_count" in data
        assert "unassigned_count" in data
        assert "vehicles_used" in data
        assert "total_distance_km" in data
        assert "total_time_minutes" in data
        assert "matrix_source" in data
        assert isinstance(data["vehicles"], list)
        assert isinstance(data["unassigned"], list)

    def test_success_has_job_id(self, client, sample_request):
        resp = client.post("/api/v1/optimize-routes", json=sample_request)
        assert resp.json()["job_id"] is not None

    def test_success_uses_provided_job_id(self, client, sample_request):
        req = {**sample_request, "job_id": "my-custom-id"}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.json()["job_id"] == "my-custom-id"

    def test_duplicate_delivery_ids_returns_422(self, client):
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

    def test_depot_id_conflict_returns_422(self, client):
        req = {
            "depot": {"id": 1, "lat": 51.5074, "lon": -0.1278, "demand": 0},
            "deliveries": [{"id": 1, "lat": 51.51, "lon": -0.07, "demand": 1}],
            "vehicles": {"count": 2, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
        }
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_invalid_vehicle_count_returns_422(self, client, sample_request):
        req = {
            **sample_request,
            "vehicles": {"count": 0, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
        }
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_vehicle_count_above_max_returns_422(self, client, sample_request):
        req = {
            **sample_request,
            "vehicles": {"count": 101, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
        }
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_empty_deliveries_returns_422(self, client):
        req = {
            "depot": {"id": 0, "lat": 51.5074, "lon": -0.1278, "demand": 0},
            "deliveries": [],
            "vehicles": {"count": 2, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
        }
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_missing_depot_returns_422(self, client):
        req = {
            "deliveries": [{"id": 1, "lat": 51.51, "lon": -0.07, "demand": 1}],
            "vehicles": {"count": 2, "capacity": 50, "max_route_duration_seconds": 9000, "speed_kmh": 30},
        }
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_invalid_lat_returns_422(self, client, sample_request):
        req = {**sample_request, "depot": {"id": 0, "lat": 100, "lon": 0, "demand": 0}}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_invalid_lon_returns_422(self, client, sample_request):
        req = {**sample_request, "depot": {"id": 0, "lat": 0, "lon": 200, "demand": 0}}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_negative_demand_returns_422(self, client, sample_request):
        req = {**sample_request, "deliveries": [{"id": 1, "lat": 51.51, "lon": -0.07, "demand": -1}]}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_delivery_count_exceeds_max_returns_422(self, client, sample_request):
        deliveries = [{"id": i, "lat": 51.5, "lon": -0.1, "demand": 1} for i in range(1001)]
        req = {**sample_request, "deliveries": deliveries}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_invalid_json_body_returns_422(self, client):
        resp = client.post("/api/v1/optimize-routes", content=b"not-json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_routing_backend_override(self, client, sample_request):
        req = {**sample_request, "routing_backend": "haversine"}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 200

    def test_invalid_routing_backend_returns_422(self, client, sample_request):
        req = {**sample_request, "routing_backend": "invalid-backend"}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422

    def test_traffic_requires_ors_api_key(self, client, sample_request, monkeypatch):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "ORS_API_KEY", "")
        req = {**sample_request, "routing_backend": "ors", "traffic": True}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422
        assert "ORS_API_KEY" in resp.json()["detail"]

    def test_traffic_requires_ors_backend(self, client, sample_request, monkeypatch):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "ORS_API_KEY", "test-key")
        req = {**sample_request, "routing_backend": "haversine", "traffic": True}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 422
        assert "'ors'" in resp.json()["detail"]

    def test_traffic_with_ors_backend_and_key_succeeds(self, client, sample_request, monkeypatch):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "ORS_API_KEY", "test-key")
        req = {**sample_request, "routing_backend": "ors", "traffic": True}
        resp = client.post("/api/v1/optimize-routes", json=req)
        assert resp.status_code == 200

    def test_response_has_vehicles_list(self, client, sample_request):
        resp = client.post("/api/v1/optimize-routes", json=sample_request)
        vehicles = resp.json()["vehicles"]
        assert len(vehicles) > 0
        for v in vehicles:
            assert "vehicle_id" in v
            assert "route" in v
            assert "distance_km" in v
            assert "time_minutes" in v
            assert "packages_delivered" in v

    def test_total_locations_matches_input(self, client, sample_request):
        resp = client.post("/api/v1/optimize-routes", json=sample_request)
        assert resp.json()["total_locations"] == 2

    def test_solver_time_is_positive(self, client, sample_request):
        resp = client.post("/api/v1/optimize-routes", json=sample_request)
        assert resp.json()["solver_time_seconds"] > 0

    def test_content_type_is_json(self, client, sample_request):
        resp = client.post("/api/v1/optimize-routes", json=sample_request)
        assert resp.headers["content-type"] == "application/json"


# ─────────────────────────────────────────────
# GET /api/v1/routes/{job_id}
# ─────────────────────────────────────────────


class TestGetRoutes:
    def test_get_existing_job_returns_200(self, client, sample_request):
        create_resp = client.post("/api/v1/optimize-routes", json=sample_request)
        job_id = create_resp.json()["job_id"]
        resp = client.get(f"/api/v1/routes/{job_id}")
        assert resp.status_code == 200

    def test_get_existing_job_matches_id(self, client, sample_request):
        create_resp = client.post("/api/v1/optimize-routes", json=sample_request)
        job_id = create_resp.json()["job_id"]
        resp = client.get(f"/api/v1/routes/{job_id}")
        assert resp.json()["job_id"] == job_id

    def test_get_existing_job_full_response(self, client, sample_request):
        create_resp = client.post("/api/v1/optimize-routes", json=sample_request)
        job_id = create_resp.json()["job_id"]
        resp = client.get(f"/api/v1/routes/{job_id}")
        data = resp.json()
        assert data["status"] == "success"
        assert "solver_time_seconds" in data
        assert "vehicles" in data
        assert "unassigned" in data

    def test_get_nonexistent_job_returns_404(self, client):
        resp = client.get("/api/v1/routes/nonexistent-id")
        assert resp.status_code == 404

    def test_get_nonexistent_job_error_message(self, client):
        resp = client.get("/api/v1/routes/nonexistent-id")
        assert "detail" in resp.json()

    def test_get_job_with_empty_id_redirects_to_list(self, client):
        resp = client.get("/api/v1/routes/", follow_redirects=False)
        assert resp.status_code == 307

    def test_get_job_preserves_data_across_calls(self, client, sample_request):
        create_resp = client.post("/api/v1/optimize-routes", json=sample_request)
        job_id = create_resp.json()["job_id"]
        resp1 = client.get(f"/api/v1/routes/{job_id}")
        resp2 = client.get(f"/api/v1/routes/{job_id}")
        assert resp1.json() == resp2.json()


# ─────────────────────────────────────────────
# GET /api/v1/routes
# ─────────────────────────────────────────────


class TestListRoutes:
    def test_list_returns_200(self, client):
        resp = client.get("/api/v1/routes")
        assert resp.status_code == 200

    def test_list_has_count_and_jobs(self, client):
        resp = client.get("/api/v1/routes")
        data = resp.json()
        assert "count" in data
        assert "jobs" in data

    def test_list_count_is_integer(self, client):
        resp = client.get("/api/v1/routes")
        assert isinstance(resp.json()["count"], int)

    def test_list_jobs_is_list(self, client):
        resp = client.get("/api/v1/routes")
        assert isinstance(resp.json()["jobs"], list)

    def test_list_returns_jobs_after_optimization(self, client, sample_request):
        client.post("/api/v1/optimize-routes", json=sample_request)
        resp = client.get("/api/v1/routes")
        assert resp.json()["count"] >= 1

    def test_list_summary_has_expected_fields(self, client, sample_request):
        client.post("/api/v1/optimize-routes", json=sample_request)
        resp = client.get("/api/v1/routes")
        job = resp.json()["jobs"][0]
        assert "job_id" in job
        assert "status" in job
        assert "total_locations" in job
        assert "vehicles_used" in job
        assert "solver_time_seconds" in job

    def test_list_respects_limit_param(self, client, sample_request):
        for _ in range(3):
            client.post("/api/v1/optimize-routes", json=sample_request)
        resp = client.get("/api/v1/routes?limit=2")
        assert resp.json()["count"] <= 2

    def test_list_limit_min_1(self, client):
        resp = client.get("/api/v1/routes?limit=0")
        assert resp.status_code == 422

    def test_list_limit_max_100(self, client):
        resp = client.get("/api/v1/routes?limit=101")
        assert resp.status_code == 422

    def test_list_limit_negative_returns_422(self, client):
        resp = client.get("/api/v1/routes?limit=-1")
        assert resp.status_code == 422

    def test_list_empty_when_no_jobs(self, client):
        resp = client.get("/api/v1/routes")
        assert resp.json()["count"] == 0
        assert resp.json()["jobs"] == []


# ─────────────────────────────────────────────
# Cross-tenant isolation (job results are company-scoped)
# ─────────────────────────────────────────────


class TestCrossTenantIsolation:
    def test_job_result_not_leaked_across_companies(self, client, sample_request):
        create_resp = client.post("/api/v1/optimize-routes", json=sample_request)
        job_id = create_resp.json()["job_id"]

        other_user = MagicMock()
        other_user.company_id = "00000000-0000-0000-0000-000000000002"
        client.app.dependency_overrides[get_current_principal] = lambda: other_user

        resp = client.get(f"/api/v1/routes/{job_id}")
        assert resp.status_code == 404

    def test_job_result_visible_to_own_company(self, client, sample_request):
        create_resp = client.post("/api/v1/optimize-routes", json=sample_request)
        job_id = create_resp.json()["job_id"]
        resp = client.get(f"/api/v1/routes/{job_id}")
        assert resp.status_code == 200

    async def test_get_job_from_db_rejects_invalid_uuid(self):
        from app.services.job_store import get_job_from_db

        db = MagicMock()
        result = await get_job_from_db(db, "not-a-uuid", _DEFAULT_COMPANY_ID)
        assert result is None
        db.execute.assert_not_called()


# ─────────────────────────────────────────────
# Rate limit headers (applied to all non-meta routes)
# ─────────────────────────────────────────────


class TestRateLimitHeaders:
    def test_rate_limit_headers_present_on_routes(self, client):
        resp = client.get("/api/v1/routes")
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers

    def test_rate_limit_headers_not_on_health(self, client):
        resp = client.get("/health")
        assert "X-RateLimit-Limit" not in resp.headers

    def test_rate_limit_headers_not_on_root(self, client):
        resp = client.get("/")
        assert "X-RateLimit-Limit" not in resp.headers

    def test_rate_limit_remaining_decreases(self, client):
        resp1 = client.get("/api/v1/routes")
        remaining1 = int(resp1.headers["X-RateLimit-Remaining"])
        resp2 = client.get("/api/v1/routes")
        remaining2 = int(resp2.headers["X-RateLimit-Remaining"])
        assert remaining2 < remaining1

    def test_rate_limit_values_are_positive_integers(self, client):
        resp = client.get("/api/v1/routes")
        assert int(resp.headers["X-RateLimit-Limit"]) > 0
        assert int(resp.headers["X-RateLimit-Remaining"]) >= 0


# ─────────────────────────────────────────────
# Global error handling
# ─────────────────────────────────────────────


class TestErrorHandling:
    def test_not_found_returns_json(self, client):
        resp = client.get("/nonexistent")
        assert resp.headers["content-type"] == "application/json"

    def test_not_found_has_detail(self, client):
        resp = client.get("/nonexistent")
        assert "detail" in resp.json()

    def test_method_not_allowed_returns_405(self, client):
        resp = client.put("/api/v1/routes")
        assert resp.status_code == 405

    def test_server_error_returns_500(self, client):
        with patch("app.routes.optimization.run_optimization_sync", side_effect=RuntimeError("boom")):
            resp = client.post(
                "/api/v1/optimize-routes",
                json={
                    "depot": {"id": 0, "lat": 0, "lon": 0, "demand": 0},
                    "deliveries": [{"id": 1, "lat": 1, "lon": 1, "demand": 1}],
                    "vehicles": {"count": 1, "capacity": 10, "max_route_duration_seconds": 9000, "speed_kmh": 30},
                },
            )
        assert resp.status_code == 500

    def test_server_error_does_not_leak_details(self, client):
        with patch("app.routes.optimization.run_optimization_sync", side_effect=RuntimeError("boom")):
            resp = client.post(
                "/api/v1/optimize-routes",
                json={
                    "depot": {"id": 0, "lat": 0, "lon": 0, "demand": 0},
                    "deliveries": [{"id": 1, "lat": 1, "lon": 1, "demand": 1}],
                    "vehicles": {"count": 1, "capacity": 10, "max_route_duration_seconds": 9000, "speed_kmh": 30},
                },
            )
        assert "boom" not in resp.text
        assert "Internal server error" not in resp.text


# ─────────────────────────────────────────────


class TestDirectionsEndpoint:
    def _seed_job(self):
        from app.services import cache

        resp = OptimizeResponse(
            job_id="dir-test",
            status="success",
            solver_time_seconds=0.123,
            total_locations=3,
            assigned_count=3,
            unassigned_count=0,
            vehicles_used=1,
            total_distance_km=45.0,
            total_time_minutes=90.0,
            vehicles=[
                VehicleRoute(
                    vehicle_id=1,
                    route=[0, 1, 2, 0],
                    route_labels=["Depot", "Stop 1", "Stop 2", "Depot"],
                    distance_km=45.0,
                    time_minutes=90.0,
                    packages_delivered=2,
                    waypoints=[
                        {"id": 0, "lat": 51.5074, "lon": -0.1278, "priority": 1},
                        {"id": 1, "lat": 51.5089, "lon": -0.1301, "priority": 1},
                        {"id": 2, "lat": 51.5100, "lon": -0.1320, "priority": 1},
                    ],
                ),
            ],
            unassigned=[],
            unassigned_labels=[],
            matrix_source="haversine",
        )
        cache.set_job("00000000-0000-0000-0000-000000000001", resp.job_id, resp.model_dump())

    def test_directions_returns_steps_for_route(self, client):
        self._seed_job()
        resp = client.get("/api/v1/routes/dir-test/directions/route/0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "dir-test"
        assert data["route_index"] == 0
        assert data["source"] == "haversine"
        assert len(data["steps"]) == 3
        assert data["steps"][0]["instruction"] == "Proceed to waypoint"
        assert data["geometry"], "expected a polyline"

    def test_directions_404_for_missing_job(self, client):
        resp = client.get("/api/v1/routes/nope/directions/route/0")
        assert resp.status_code == 404

    def test_directions_404_for_bad_route_index(self, client):
        self._seed_job()
        resp = client.get("/api/v1/routes/dir-test/directions/route/9")
        assert resp.status_code == 404


class TestExportEndpoint:
    def _seed_job(self):
        from app.services import cache

        resp = _make_fake_response(job_id="export-test")
        resp.vehicles[0].waypoints = [
            {"id": 0, "lat": 51.5074, "lon": -0.1278},
            {"id": 1, "lat": 51.5089, "lon": -0.1301},
            {"id": 2, "lat": 51.5100, "lon": -0.1320},
            {"id": 0, "lat": 51.5074, "lon": -0.1278},
        ]
        cache.set_job("00000000-0000-0000-0000-000000000001", resp.job_id, resp.model_dump())

    def test_export_csv_includes_direction_columns(self, client):
        self._seed_job()
        resp = client.get("/api/v1/routes/export-test/export?format=csv")
        assert resp.status_code == 200
        assert "arrive_maneuver" in resp.text
        assert "arrive_instruction" in resp.text
        assert "Proceed to waypoint" in resp.text  # haversine fallback steps

    def test_export_kml(self, client):
        self._seed_job()
        resp = client.get("/api/v1/routes/export-test/export?format=kml")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/vnd.google-earth.kml+xml")
        assert "<kml" in resp.text
        assert "Leg 1" in resp.text

    def test_export_gpx_still_works(self, client):
        self._seed_job()
        resp = client.get("/api/v1/routes/export-test/export?format=gpx")
        assert resp.status_code == 200
        assert "<gpx" in resp.text

    def test_export_unknown_format_422(self, client):
        self._seed_job()
        resp = client.get("/api/v1/routes/export-test/export?format=docx")
        assert resp.status_code == 422

    def test_export_missing_job_404(self, client):
        resp = client.get("/api/v1/routes/nope/export?format=kml")
        assert resp.status_code == 404


# ─────────────────────────────────────────────
# POST /api/v1/drivers/{driver_id}/stops/{stop_id}/status
# ─────────────────────────────────────────────

_DRIVER_ID = "00000000-0000-0000-0000-000000000003"
_STOP_JOB_ID = "stop-status-test"


def _stop_status_route_json() -> dict:
    return {
        "vehicle_id": 1,
        "route": [0, 1, 2, 0],
        "route_labels": ["Depot", "Stop 1", "Stop 2", "Depot"],
        "distance_km": 45.0,
        "time_minutes": 90.0,
        "packages_delivered": 2,
        "waypoints": [
            {"id": 0, "lat": 51.5074, "lon": -0.1278, "priority": 1, "status": "pending"},
            {"id": 1, "lat": 51.5089, "lon": -0.1301, "priority": 1, "status": "pending"},
            {"id": 2, "lat": 51.5100, "lon": -0.1320, "priority": 1, "status": "pending"},
            {"id": 0, "lat": 51.5074, "lon": -0.1278, "priority": 1, "status": "pending"},
        ],
        "arrival_times": [0, 1800, 3600],
    }


def _seed_stop_job() -> None:
    from app.services import cache

    routes = _stop_status_route_json()
    resp = {
        "job_id": _STOP_JOB_ID,
        "status": "success",
        "solver_time_seconds": 0.1,
        "total_locations": 2,
        "assigned_count": 2,
        "unassigned_count": 0,
        "vehicles_used": 1,
        "total_distance_km": 45.0,
        "total_time_minutes": 90.0,
        "vehicles": [routes],
        "unassigned": [],
        "unassigned_labels": [],
        "matrix_source": "haversine",
    }
    cache.set_job(_DEFAULT_COMPANY_ID, _STOP_JOB_ID, resp)


class TestStopStatusEndpoint:
    @pytest.fixture
    def env(self):
        from app.database import get_db
        from app.dependencies import require_user
        from app.models.db import Driver, VehicleRoute

        app = create_app()
        mock_user = MagicMock()
        mock_user.company_id = _DEFAULT_COMPANY_ID

        driver = Driver(
            id=_DRIVER_ID,
            company_id=_DEFAULT_COMPANY_ID,
            name="Joan",
            phone="+15550123",
            status="on_route",
        )
        vr = VehicleRoute(
            job_id=_STOP_JOB_ID,
            vehicle_id=1,
            route_json=_stop_status_route_json(),
            distance_km=45.0,
            time_minutes=90.0,
            packages=2,
        )

        async def _execute(stmt):
            s = str(stmt)
            out = MagicMock()
            if "FROM drivers" in s:
                out.scalar_one_or_none.return_value = driver
            elif "FROM vehicle_routes" in s:
                # `_get_assigned_route` sorts; the persist path doesn't — both may
                # return the same route row here.
                out.scalar_one_or_none.return_value = vr
            else:  # optimization_jobs etc.
                out.scalar_one_or_none.return_value = None
            return out

        state = {"db": AsyncMock(), "sent_triggers": [], "driver": driver}
        state["db"].execute.side_effect = _execute

        async def _fake_db():
            yield state["db"]

        app.dependency_overrides[require_user] = lambda: mock_user
        app.dependency_overrides[get_db] = _fake_db

        async def fake_send(db, company_id, driver_id, trigger, *args, **kwargs):
            state["sent_triggers"].append(trigger)
            return [{"channel": "sms", "recipient": None, "status": "sent"}]

        state["send"] = AsyncMock(side_effect=fake_send)
        with patch("app.services.stop_lifecycle.send_notification", state["send"]), TestClient(app) as c:
            yield c, state
        app.dependency_overrides.clear()
        from app.services import cache

        cache._job_cache.clear()

    def _post(self, c, stop_id=1, status="en_route"):
        return c.post(f"/api/v1/drivers/{_DRIVER_ID}/stops/{stop_id}/status", json={"status": status})

    def test_en_route_transitions_stop_and_persists(self, env):
        c, state = env
        _seed_stop_job()
        resp = self._post(c, stop_id=1, status="en_route")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stop_id"] == 1
        assert data["previous_status"] == "pending"
        assert data["status"] == "en_route"

        from app.services import cache

        cached = cache.get_job(_DEFAULT_COMPANY_ID, _STOP_JOB_ID)
        wp = [w for w in cached["vehicles"][0]["waypoints"] if w["id"] == 1][0]
        assert wp["status"] == "en_route"

    def test_arrived_emits_arrived_trigger(self, env):
        c, state = env
        _seed_stop_job()
        assert self._post(c, stop_id=1, status="en_route").status_code == 200
        resp = self._post(c, stop_id=1, status="arrived")
        assert resp.status_code == 200
        assert resp.json()["previous_status"] == "en_route"
        assert state["sent_triggers"] == ["arrived"]

    def test_out_of_order_transition_returns_409(self, env):
        c, state = env
        _seed_stop_job()
        resp = self._post(c, stop_id=1, status="arrived")
        assert resp.status_code == 409
        assert "Invalid transition" in resp.json()["detail"]

        from app.services import cache

        cached = cache.get_job(_DEFAULT_COMPANY_ID, _STOP_JOB_ID)
        wp = [w for w in cached["vehicles"][0]["waypoints"] if w["id"] == 1][0]
        assert wp["status"] == "pending"

    def test_unknown_stop_returns_404(self, env):
        c, state = env
        _seed_stop_job()
        resp = self._post(c, stop_id=99, status="en_route")
        assert resp.status_code == 404

    def test_invalid_status_value_returns_422(self, env):
        c, state = env
        _seed_stop_job()
        resp = c.post(f"/api/v1/drivers/{_DRIVER_ID}/stops/1/status", json={"status": "shipped"})
        assert resp.status_code == 422

    def test_unassigned_driver_returns_404(self, env):
        c, state = env
        _seed_stop_job()

        async def _no_route(stmt):
            out = MagicMock()
            out.scalar_one_or_none.return_value = None
            return out

        state["db"].execute.side_effect = _no_route
        resp = self._post(c, stop_id=1, status="en_route")
        assert resp.status_code == 404

    def test_delayed_trigger_when_running_late(self, env):
        c, state = env
        _seed_stop_job()
        state["driver"].current_lat = 51.5070
        state["driver"].current_lon = -0.1280
        eta = {"remaining_stops": [{"id": 2, "delta_min": 32.0}]}
        with patch("app.services.stop_lifecycle.compute_live_eta", AsyncMock(return_value=eta)):
            assert self._post(c, stop_id=1, status="en_route").status_code == 200
            resp = self._post(c, stop_id=1, status="arrived")
        assert resp.status_code == 200
        # en_route → delayed (late to a remaining stop); arrived → arrived + delayed
        assert state["sent_triggers"] == ["delayed", "arrived", "delayed"]
