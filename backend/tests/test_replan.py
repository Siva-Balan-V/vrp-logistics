"""Tests for ride-along re-optimization (Phase 8.6)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import require_principal
from app.main import create_app
from app.models.schemas import OptimizeResponse, ReplanDriver, ReplanRequest, VehicleRoute, VehicleSpec
from app.services import replan

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DRIVER_A = uuid.UUID("00000000-0000-0000-0000-000000000003")
_DRIVER_B = uuid.UUID("00000000-0000-0000-0000-000000000004")
_PREV_JOB_ID = "f2ec6a8e-59be-4caf-bda1-5e1e6b2f1d9a"

_DEPOT = {"id": 0, "lat": 51.5074, "lon": -0.1278, "priority": 1}
_STOP_1 = {"id": 1, "lat": 51.51, "lon": -0.07, "priority": 1}
_STOP_2 = {"id": 2, "lat": 51.52, "lon": -0.08, "priority": 2}
_STOP_3 = {"id": 3, "lat": 51.53, "lon": -0.09, "priority": 1}
_STOP_4 = {"id": 4, "lat": 51.54, "lon": -0.10, "priority": 1}


def _route_dict(vehicle_id: int, waypoints: list[dict], stop_ids: list[int]) -> dict:
    return {
        "vehicle_id": vehicle_id,
        "route": [0] + stop_ids + [0],
        "route_labels": ["Depot"] + [f"Stop {i}" for i in stop_ids] + ["Depot"],
        "distance_km": 45.0,
        "time_minutes": 90.0,
        "packages_delivered": len(stop_ids),
        "waypoints": waypoints,
        "arrival_times": [0, 1800, 3600, 0],
    }


def _with_status(stop: dict, status: str) -> dict:
    return {**stop, "status": status}


def _previous_response(status_by_stop: dict[int, str], unassigned: list[int] | None = None) -> OptimizeResponse:
    """Sample previous job: stops 1+2 on vehicle 1, 3+4 on vehicle 2."""
    wp1 = [
        _DEPOT,
        _with_status(_STOP_1, status_by_stop.get(1, "pending")),
        _with_status(_STOP_2, status_by_stop.get(2, "pending")),
        _DEPOT,
    ]
    wp2 = [
        _DEPOT,
        _with_status(_STOP_3, status_by_stop.get(3, "pending")),
        _with_status(_STOP_4, status_by_stop.get(4, "pending")),
        _DEPOT,
    ]
    unassigned = unassigned or []
    return OptimizeResponse(
        job_id=_PREV_JOB_ID,
        status="success",
        solver_time_seconds=0.1,
        total_locations=4,
        assigned_count=4 - len(unassigned),
        unassigned_count=len(unassigned),
        vehicles_used=2,
        total_distance_km=90.0,
        total_time_minutes=180.0,
        vehicles=[
            VehicleRoute(**_route_dict(1, wp1, [1, 2])),
            VehicleRoute(**_route_dict(2, wp2, [3, 4])),
        ],
        unassigned=unassigned,
        unassigned_labels=[],
        matrix_source="haversine",
    )


def _fake_result(**overrides) -> OptimizeResponse:
    overrides = dict(overrides)
    job_id = overrides.pop("job_id", "new-job-123")
    return OptimizeResponse(
        job_id=job_id,
        status="success",
        solver_time_seconds=0.2,
        total_locations=2,
        assigned_count=2,
        unassigned_count=0,
        vehicles_used=1,
        total_distance_km=30.0,
        total_time_minutes=60.0,
        vehicles=[
            VehicleRoute(
                vehicle_id=1,
                route=[-1, 1, 3, -1],
                route_labels=["Driver start", "Stop 1", "Stop 3", "Driver start"],
                distance_km=30.0,
                time_minutes=60.0,
                packages_delivered=2,
                waypoints=[
                    {**_DEPOT, "id": -1, "status": "pending"},
                    {**_STOP_1, "status": "pending"},
                    {**_STOP_3, "status": "pending"},
                    {**_DEPOT, "id": -1, "status": "pending"},
                ],
                arrival_times=[0, 1200, 2400, 0],
            ),
        ],
        unassigned=[],
        unassigned_labels=[],
        matrix_source="haversine",
        **overrides,
    )


@pytest.fixture(autouse=True)
def clear_cache():
    from app.services.cache import _job_cache

    _job_cache.clear()
    yield
    _job_cache.clear()


# ─────────────────────────────────────────────
# Remaining-stop selection
# ─────────────────────────────────────────────


class TestCollectRemainingStops:
    def test_delivered_stops_excluded(self):
        previous = _previous_response(status_by_stop={2: "delivered", 4: "delivered"})
        ids = [loc.id for loc in replan._collect_remaining_stops(previous, None)]
        assert ids == [1, 3]
        assert 2 not in ids
        assert 4 not in ids

    def test_depot_waypoints_never_included(self):
        previous = _previous_response(status_by_stop={})
        ids = [loc.id for loc in replan._collect_remaining_stops(previous, None)]
        assert ids == [1, 2, 3, 4]
        assert 0 not in ids  # depot id

    def test_unassigned_stops_pulled_back_in_when_request_known(self):
        wp2 = [_DEPOT, _with_status(_STOP_3, "pending"), _DEPOT]
        previous = OptimizeResponse(
            job_id=_PREV_JOB_ID,
            status="success",
            solver_time_seconds=0.1,
            total_locations=4,
            assigned_count=3,
            unassigned_count=1,
            vehicles_used=2,
            total_distance_km=60.0,
            total_time_minutes=120.0,
            vehicles=[
                VehicleRoute(
                    **_route_dict(
                        1,
                        [
                            _DEPOT,
                            _with_status(_STOP_1, "delivered"),
                            _with_status(_STOP_2, "pending"),
                            _DEPOT,
                        ],
                        [1, 2],
                    )
                ),
                VehicleRoute(**_route_dict(2, wp2, [3])),
            ],
            unassigned=[4],
            unassigned_labels=[],
            matrix_source="haversine",
        )
        req_dict = {
            "job_id": _PREV_JOB_ID,
            "depots": [{**_DEPOT, "demand": 0}],
            "deliveries": [
                {**_STOP_1, "demand": 1},
                {**_STOP_2, "demand": 1},
                {**_STOP_3, "demand": 1},
                {**_STOP_4, "demand": 1},
            ],
            "vehicles": {},
        }
        ids = [loc.id for loc in replan._collect_remaining_stops(previous, req_dict)]
        assert 1 not in ids  # delivered
        assert 2 in ids
        assert 3 in ids
        assert 4 in ids  # previously unassigned, coords recovered via request

    def test_falls_back_to_waypoint_coords_without_request(self):
        previous = _previous_response(status_by_stop={})
        locs = {loc.id: loc for loc in replan._collect_remaining_stops(previous, None)}
        assert locs[1].lat == 51.51
        assert locs[1].demand == 1  # waypoints don't carry demand — default
        assert locs[2].priority == 2


# ─────────────────────────────────────────────
# Start-position seeding
# ─────────────────────────────────────────────


class TestBuildDepotLocations:
    def test_driver_positions_become_synthetic_depots(self):
        previous = _previous_response(status_by_stop={})
        drivers = [ReplanDriver(driver_id=_DRIVER_A, lat=51.509, lon=-0.096)]
        depots = replan._build_depot_locations(previous, None, drivers)
        assert [d.id for d in depots] == [-1]
        assert depots[0].lat == 51.509
        assert depots[0].demand == 0

    def test_multiple_drivers_get_distinct_depot_ids(self):
        drivers = [
            ReplanDriver(driver_id=_DRIVER_A, lat=51.509, lon=-0.096),
            ReplanDriver(driver_id=_DRIVER_B, lat=51.519, lon=-0.106),
        ]
        depots = replan._build_depot_locations(_previous_response({}), None, drivers)
        assert [d.id for d in depots] == [-1, -2]
        assert len({d.id for d in depots}) == 2

    def test_falls_back_to_previous_depots_without_drivers(self):
        previous = _previous_response(status_by_stop={})
        req_dict = {
            "job_id": _PREV_JOB_ID,
            "depots": [{**_DEPOT, "demand": 0}],
            "deliveries": [{**_STOP_1, "demand": 1}],
            "vehicles": {},
        }
        depots = replan._build_depot_locations(previous, req_dict, [])
        assert depots[0].id == 0
        assert depots[0].lat == 51.5074


class TestResolveVehicleSpec:
    def test_no_override_uses_defaults(self):
        req = ReplanRequest(previous_job_id=_PREV_JOB_ID)
        assert replan._resolve_vehicle_spec(req, None).count == 18  # VehicleSpec default

    def test_uses_previous_request_spec(self):
        req = ReplanRequest(previous_job_id=_PREV_JOB_ID)
        req_dict = {
            "depots": [{**_DEPOT, "demand": 0}],
            "deliveries": [{**_STOP_1, "demand": 1}],
            "vehicles": {"count": 4, "capacity": 10},
        }
        spec = replan._resolve_vehicle_spec(req, req_dict)
        assert spec.count == 4
        assert spec.capacity == 10

    def test_count_bumped_to_cover_drivers(self):
        drivers = [
            ReplanDriver(driver_id=_DRIVER_A, lat=1.0, lon=1.0),
            ReplanDriver(driver_id=_DRIVER_B, lat=2.0, lon=2.0),
        ]
        req = ReplanRequest(
            previous_job_id=_PREV_JOB_ID,
            drivers=drivers,
            vehicles=VehicleSpec(count=1, capacity=5),
        )
        spec = replan._resolve_vehicle_spec(req, None)
        assert spec.count == 2  # bumped from 1 to give each driver a start


# ─────────────────────────────────────────────
# run_replan orchestration
# ─────────────────────────────────────────────


class TestRunReplan:
    async def test_remaining_subset_solved_with_driver_starts(self):
        from app.services import cache

        previous = _previous_response(status_by_stop={2: "delivered", 4: "delivered"})
        cache.set_job(_COMPANY_ID, _PREV_JOB_ID, previous.model_dump())

        captured = {}

        def fake_solve(req, run_id=None, company_id=None):
            captured["req"] = req
            return _fake_result(job_id=req.job_id)

        req = ReplanRequest(
            previous_job_id=_PREV_JOB_ID,
            drivers=[ReplanDriver(driver_id=_DRIVER_A, lat=51.509, lon=-0.096)],
        )
        with patch("app.services.replan.run_optimization_sync", side_effect=fake_solve):
            await replan.run_replan(AsyncMock(), _COMPANY_ID, req)

        sub = captured["req"]
        assert sorted(d.id for d in sub.deliveries) == [1, 3]  # 2 and 4 delivered → excluded
        assert [d.id for d in sub.depots] == [-1]  # driver position seeded as start depot
        assert sub.depots[0].lat == 51.509

    async def test_result_is_linked_to_previous_job(self):
        from app.services import cache

        cache.set_job(_COMPANY_ID, _PREV_JOB_ID, _previous_response({}).model_dump())
        with patch("app.services.replan.run_optimization_sync", return_value=_fake_result()):
            result = await replan.run_replan(AsyncMock(), _COMPANY_ID, ReplanRequest(previous_job_id=_PREV_JOB_ID))
        assert result.previous_job_id == _PREV_JOB_ID

    async def test_new_job_cached_with_previous_link(self):
        from app.services import cache

        cache.set_job(_COMPANY_ID, _PREV_JOB_ID, _previous_response({}).model_dump())
        with patch("app.services.replan.run_optimization_sync", return_value=_fake_result(job_id="brand-new-id")):
            await replan.run_replan(AsyncMock(), _COMPANY_ID, ReplanRequest(previous_job_id=_PREV_JOB_ID))
        assert cache.get_job(_COMPANY_ID, "brand-new-id")["previous_job_id"] == _PREV_JOB_ID

    async def test_previous_job_missing_raises(self):
        with pytest.raises(replan.PreviousJobNotFoundError):
            await replan.run_replan(AsyncMock(), _COMPANY_ID, ReplanRequest(previous_job_id="unknown-job"))

    async def test_all_delivered_raises_value_error(self):
        from app.services import cache

        previous = _previous_response(status_by_stop={1: "delivered", 2: "delivered", 3: "delivered", 4: "delivered"})
        cache.set_job(_COMPANY_ID, _PREV_JOB_ID, previous.model_dump())
        with patch("app.services.replan.run_optimization_sync"), pytest.raises(ValueError, match="nothing to re-plan"):
            await replan.run_replan(AsyncMock(), _COMPANY_ID, ReplanRequest(previous_job_id=_PREV_JOB_ID))

    async def test_persists_new_job_with_link_when_db_enabled(self):
        from app.services import cache

        cache.set_job(_COMPANY_ID, _PREV_JOB_ID, _previous_response({}).model_dump())
        db = AsyncMock()

        async def _execute(_stmt):
            out = MagicMock()
            out.scalar_one_or_none.return_value = None
            return out

        db.execute.side_effect = _execute
        req = ReplanRequest(previous_job_id=_PREV_JOB_ID)
        with (
            patch("app.services.replan.run_optimization_sync", return_value=_fake_result()),
            patch("app.services.replan.is_db_enabled", return_value=True),
            patch("app.services.replan.persist_job", new_callable=AsyncMock) as persist,
        ):
            await replan.run_replan(db, _COMPANY_ID, req)

        persist.assert_awaited_once()
        assert persist.await_args.kwargs["previous_job_id"] == _PREV_JOB_ID
        assert persist.await_args.kwargs["company_id"] == _COMPANY_ID


# ─────────────────────────────────────────────
# API endpoint
# ─────────────────────────────────────────────


@pytest.fixture
def client():
    app = create_app()
    mock_user = MagicMock()
    mock_user.company_id = str(_COMPANY_ID)
    app.dependency_overrides[require_principal] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestReplanEndpoint:
    def test_replan_returns_200(self, client):
        from app.services import cache

        cache.set_job(_COMPANY_ID, _PREV_JOB_ID, _previous_response(status_by_stop={2: "delivered"}).model_dump())
        payload = {
            "previous_job_id": _PREV_JOB_ID,
            "drivers": [
                {"driver_id": str(_DRIVER_A), "lat": 51.509, "lon": -0.096},
                {"driver_id": str(_DRIVER_B), "lat": 51.519, "lon": -0.106},
            ],
        }

        def fake_solve(db, company_id, req):
            return _fake_result(previous_job_id=req.previous_job_id)

        with patch("app.routes.optimization.run_replan", side_effect=fake_solve):
            resp = client.post("/api/v1/optimize-routes/replan", json=payload)
        assert resp.status_code == 200
        assert resp.json()["previous_job_id"] == _PREV_JOB_ID

    def test_missing_previous_job_returns_404(self, client):
        with patch(
            "app.routes.optimization.run_replan",
            side_effect=replan.PreviousJobNotFoundError("No result found for job_id=no-such-job."),
        ):
            resp = client.post("/api/v1/optimize-routes/replan", json={"previous_job_id": "no-such-job"})
        assert resp.status_code == 404

    def test_all_delivered_returns_422(self, client):
        with patch("app.routes.optimization.run_replan", side_effect=ValueError("nothing to re-plan")):
            resp = client.post("/api/v1/optimize-routes/replan", json={"previous_job_id": _PREV_JOB_ID})
        assert resp.status_code == 422
