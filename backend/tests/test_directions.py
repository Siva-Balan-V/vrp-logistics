"""Tests for the turn-by-turn directions service and endpoint."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schemas import DirectionsLeg, DirectionsResponse, OptimizeResponse, VehicleDirections, VehicleRoute
from app.routes.optimization import _DEFAULT_COMPANY_ID
from app.services import cache
from app.services.directions import build_osrm_instruction, build_vehicle_directions


def _fake_response(job_id: str = "dir-job", backend: str = "osrm") -> OptimizeResponse:
    waypoints = [
        {"id": 0, "lat": 51.5074, "lon": -0.1278, "priority": 1},
        {"id": 1, "lat": 51.515, "lon": -0.072, "priority": 1},
        {"id": 2, "lat": 51.508, "lon": -0.094, "priority": 1},
        {"id": 0, "lat": 51.5074, "lon": -0.1278, "priority": 1},
    ]
    return OptimizeResponse(
        job_id=job_id,
        status="success",
        solver_time_seconds=0.123,
        total_locations=2,
        assigned_count=2,
        unassigned_count=0,
        vehicles_used=1,
        total_distance_km=8.0,
        total_time_minutes=20.0,
        vehicles=[
            VehicleRoute(
                vehicle_id=1,
                route=[0, 1, 2, 0],
                route_labels=["Depot", "Stop A", "Stop B", "Depot"],
                distance_km=8.0,
                time_minutes=20.0,
                packages_delivered=2,
                waypoints=waypoints,
            ),
        ],
        unassigned=[],
        unassigned_labels=[],
        matrix_source=backend,
    )


# ── Instruction building ──────────────────────────────────────────


def test_build_osrm_instruction_turn():
    step = {"name": "High St", "maneuver": {"type": "turn", "modifier": "left"}}
    assert build_osrm_instruction(step) == "Turn left onto High St"


def test_build_osrm_instruction_depart_unknown_modifier():
    step = {"maneuver": {"type": "depart", "modifier": "east"}}
    assert build_osrm_instruction(step) == "Head straight"


def test_build_osrm_instruction_arrive():
    step = {"maneuver": {"type": "arrive"}}
    assert build_osrm_instruction(step) == "Arrive at your destination"


def test_build_osrm_instruction_roundabout_with_exit():
    step = {"name": "Roundabout", "exits": 3, "maneuver": {"type": "roundabout", "modifier": "right"}}
    assert build_osrm_instruction(step) == "In the roundabout take exit 3 onto Roundabout"


# ── Cache ─────────────────────────────────────────────────────────


def test_directions_cache_roundtrip():
    key_from, key_to = (51.0, -0.1), (51.1, -0.2)
    payload = {"distance_m": 1000.0, "duration_s": 120.0, "steps": []}
    cache.set_directions("osrm", key_from, key_to, payload)
    assert cache.get_directions("osrm", key_from, key_to) == payload
    assert cache.get_directions("osrm", key_from, key_to) is not None


def test_directions_cache_miss():
    assert cache.get_directions("ors", (52.0, 13.4), (40.7, -74.0)) is None


# ── Service ─────────────────────────────────────────────────────────


async def test_build_vehicle_directions(monkeypatch):
    async def fake_fetch(backend, from_coord, to_coord):
        return {"distance_m": 1000.0, "duration_s": 120.0, "steps": [{"instruction": "Go", "name": "A"}]}

    monkeypatch.setattr("app.services.directions.fetch_route", fake_fetch)
    vehicle = {
        "vehicle_id": 7,
        "waypoints": [
            {"id": 0, "lat": 51.0, "lon": -0.1},
            {"id": 1, "lat": 51.1, "lon": -0.2},
            {"id": 2, "lat": 51.2, "lon": -0.3},
            {"id": 0, "lat": 51.0, "lon": -0.1},
        ],
    }
    labels = ["Depot", "Stop A", "Stop B", "Depot"]
    out = await build_vehicle_directions("osrm", vehicle, labels)

    assert out["vehicle_id"] == 7
    assert len(out["legs"]) == 3
    assert out["legs"][0]["from_stop"]["label"] == "Depot"
    assert out["legs"][0]["to_stop"]["label"] == "Stop A"
    assert out["legs"][0]["distance_km"] == 1.0
    assert out["legs"][1]["to_stop"]["label"] == "Stop B"
    assert out["legs"][2]["to_stop"]["id"] == 0
    assert out["legs"][2]["to_stop"]["label"] == "Depot"


async def test_build_vehicle_directions_fallback(monkeypatch):
    async def failing_fetch_osrm(client, lon1, lat1, lon2, lat2):
        raise RuntimeError("osrm down")

    monkeypatch.setattr("app.services.directions._fetch_osrm_leg", failing_fetch_osrm)
    vehicle = {
        "vehicle_id": 2,
        "waypoints": [
            {"id": 0, "lat": 53.0, "lon": -1.0},
            {"id": 1, "lat": 53.1, "lon": -1.1},
        ],
    }
    out = await build_vehicle_directions("osrm", vehicle, ["Depot", "Stop A"])
    assert len(out["legs"]) == 1
    assert out["legs"][0]["steps"] == []
    assert out["legs"][0]["distance_km"] is None


# ── Response schema coercion ─────────────────────────────────────────


def test_directions_response_schema():
    resp = DirectionsResponse(
        job_id="x",
        backend="osrm",
        vehicles=[
            {"vehicle_id": 1, "legs": [{"from_stop": {"lat": 1.0, "lon": 2.0}, "to_stop": {"lat": 3.0, "lon": 4.0}}]}
        ],
    )
    assert isinstance(resp.vehicles[0], VehicleDirections)
    assert isinstance(resp.vehicles[0].legs[0], DirectionsLeg)


# ── Endpoint ─────────────────────────────────────────────────────────


def _client():
    return TestClient(create_app())


def test_directions_endpoint_haversine_note():
    resp = _fake_response(job_id="dir-hav", backend="haversine")
    cache.set_job(_DEFAULT_COMPANY_ID, "dir-hav", resp.model_dump())
    with _client() as client:
        r = client.get("/api/v1/routes/dir-hav/directions")
    assert r.status_code == 200
    data = r.json()
    assert data["backend"] == "haversine"
    assert "no road-network" in (data.get("note") or "")
    assert data["vehicles"][0]["legs"] == []


def test_directions_endpoint_osrm(monkeypatch):
    async def fake_fetch(backend, from_coord, to_coord):
        return {
            "distance_m": 500.0,
            "duration_s": 60.0,
            "steps": [
                {
                    "instruction": "Turn left onto Main St",
                    "name": "Main St",
                    "distance_m": 500.0,
                    "duration_s": 60.0,
                    "maneuver": "turn",
                    "modifier": "left",
                    "location": [51.5, -0.1],
                }
            ],
        }

    monkeypatch.setattr("app.services.directions.fetch_route", fake_fetch)
    resp = _fake_response(job_id="dir-osrm", backend="osrm")
    cache.set_job(_DEFAULT_COMPANY_ID, "dir-osrm", resp.model_dump())

    with _client() as client:
        r = client.get("/api/v1/routes/dir-osrm/directions")
    assert r.status_code == 200
    data = r.json()
    assert data["job_id"] == "dir-osrm"
    assert data["backend"] == "osrm"
    vehicle = data["vehicles"][0]
    assert vehicle["vehicle_id"] == 1
    assert len(vehicle["legs"]) == 3
    step = vehicle["legs"][0]["steps"][0]
    assert step["instruction"] == "Turn left onto Main St"
    assert step["location"] == [51.5, -0.1]
    # Leg endpoints come from the job's route labels
    assert vehicle["legs"][0]["from_stop"]["label"] == "Depot"
    assert vehicle["legs"][0]["to_stop"]["label"] == "Stop A"


def test_directions_endpoint_vehicle_filter(monkeypatch):
    async def fake_fetch(backend, from_coord, to_coord):
        return {"distance_m": 100.0, "duration_s": 10.0, "steps": []}

    monkeypatch.setattr("app.services.directions.fetch_route", fake_fetch)
    resp = _fake_response(job_id="dir-filter", backend="osrm")
    cache.set_job(_DEFAULT_COMPANY_ID, "dir-filter", resp.model_dump())

    with _client() as client:
        r = client.get("/api/v1/routes/dir-filter/directions?vehicle_id=999")
    assert r.status_code == 200
    assert r.json()["vehicles"] == []


def test_directions_endpoint_missing_job():
    with _client() as client:
        r = client.get("/api/v1/routes/nope/directions")
    assert r.status_code == 404
