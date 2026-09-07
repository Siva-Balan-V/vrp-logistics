"""Tests for the live fleet dispatch WebSocket channel."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from app.models.db import Driver, User, VehicleRoute
from app.services import live_dispatch
from app.websocket_manager import live_manager

_COMPANY_ID = str(uuid.UUID("00000000-0000-0000-0000-00000000000a"))
_OTHER_COMPANY_ID = str(uuid.UUID("00000000-0000-0000-0000-00000000000b"))
_USER_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
_DRIVER_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000003"))

_TOKEN_PAYLOAD = {"sub": _USER_ID, "type": "access"}


def _route_json() -> dict:
    return {
        "vehicle_id": 1,
        "route": [0, 1, 2, 0],
        "route_labels": ["Depot", "Stop 1", "Stop 2", "Depot"],
        "distance_km": 45.0,
        "time_minutes": 90.0,
        "packages_delivered": 2,
        "waypoints": [
            {"id": 0, "lat": 51.5074, "lon": -0.1278, "status": "pending"},
            {"id": 1, "lat": 51.5089, "lon": -0.1301, "status": "pending"},
            {"id": 2, "lat": 51.5100, "lon": -0.1320, "status": "pending"},
            {"id": 0, "lat": 51.5074, "lon": -0.1278, "status": "pending"},
        ],
        "arrival_times": [0, 1800, 3600],
    }


@pytest.fixture(autouse=True)
def clear_live_state():
    live_manager._subscribers.clear()
    live_dispatch._last_broadcast_ts.clear()
    yield
    live_manager._subscribers.clear()
    live_dispatch._last_broadcast_ts.clear()


def _make_app(user_company_id: str):
    app = create_app()
    user = User(id=_USER_ID, company_id=user_company_id, email="x@example.com", is_active=True)
    driver = Driver(id=_DRIVER_ID, company_id=user_company_id, name="Jane", phone="+1500", status="offline")
    vr = VehicleRoute(
        job_id="stop-status-test",
        vehicle_id=1,
        route_json=_route_json(),
        distance_km=45.0,
        time_minutes=90.0,
        packages=2,
    )

    async def _execute(stmt):
        s = str(stmt)
        out = MagicMock()
        if "FROM users" in s:
            out.scalar_one_or_none.return_value = user
        elif "FROM drivers" in s:
            out.scalar_one_or_none.return_value = driver
        elif "FROM vehicle_routes" in s:
            out.scalar_one_or_none.return_value = vr
        else:
            out.scalar_one_or_none.return_value = None
        return out

    db = AsyncMock()
    db.execute.side_effect = _execute

    async def _fake_db():
        yield db

    return app, db, user, driver, vr, _fake_db


@pytest.fixture
def app_and_db():
    from app.database import get_db as _get_db_ref

    app, db, user, driver, vr, fake_db = _make_app(_COMPANY_ID)
    app.dependency_overrides[_get_db_ref] = fake_db
    with (
        patch("app.dependencies.is_db_enabled", lambda: True),
        patch("app.database.is_db_enabled", lambda: True),
        patch("app.services.auth.decode_token", return_value=_TOKEN_PAYLOAD),
        patch("app.dependencies.decode_token", return_value=_TOKEN_PAYLOAD),
        patch("app.database.get_db", fake_db),
    ):
        yield app, db, user, driver, vr
        app.dependency_overrides.clear()


def _auth_headers():
    return {"Authorization": "Bearer tok"}


class TestDriversFleetWs:
    def test_broadcasts_position_update_to_company_channel(self, app_and_db):
        app, db, user, driver, vr = app_and_db
        with TestClient(app) as client, client.websocket_connect(f"/api/v1/ws/drivers/{_COMPANY_ID}?token=tok") as ws:
            resp = client.patch(
                f"/api/v1/drivers/{_DRIVER_ID}/location",
                json={"lat": 51.51, "lon": -0.12},
                headers=_auth_headers(),
            )
            assert resp.status_code == 200
            data = ws.receive_json()
        assert data["type"] == "driver.update"
        assert data["company_id"] == _COMPANY_ID
        assert data["driver_id"] == _DRIVER_ID
        assert data["name"] == "Jane"
        assert data["lat"] == 51.51
        assert data["lon"] == -0.12
        assert data["last_ping_at"] is not None
        assert data["status"] == "active"

    def test_broadcast_includes_live_eta(self, app_and_db):
        app, db, user, driver, vr = app_and_db
        with TestClient(app) as client, client.websocket_connect(f"/api/v1/ws/drivers/{_COMPANY_ID}?token=tok") as ws:
            client.patch(
                f"/api/v1/drivers/{_DRIVER_ID}/location",
                json={"lat": 51.5095, "lon": -0.128},
                headers=_auth_headers(),
            )
            data = ws.receive_json()
        assert data["type"] == "driver.update"
        assert "eta" in data
        assert data["eta"]["total_remaining_time_min"] is not None
        assert data["eta"]["remaining_stops"], "expected remaining stops in eta payload"

    def test_broadcast_stays_on_ping_company_channel(self, app_and_db):
        """A ping must be published only to its own company's channel."""
        app, db, user, driver, vr = app_and_db
        broadcast = AsyncMock()
        with patch.object(live_manager, "broadcast", broadcast), TestClient(app) as client:
            client.patch(
                f"/api/v1/drivers/{_DRIVER_ID}/location",
                json={"lat": 51.51, "lon": -0.12},
                headers=_auth_headers(),
            )
        broadcast.assert_awaited_once()
        assert broadcast.await_args.args[0] == _COMPANY_ID

    def test_cross_tenant_connection_rejected(self):
        """A user of company A cannot subscribe to company B's channel."""
        from app.database import get_db as _get_db_ref

        app, db, user, driver, vr, fake_db = _make_app(_COMPANY_ID)
        app.dependency_overrides[_get_db_ref] = fake_db
        with (
            patch("app.dependencies.is_db_enabled", lambda: True),
            patch("app.database.is_db_enabled", lambda: True),
            patch("app.services.auth.decode_token", return_value=_TOKEN_PAYLOAD),
            patch("app.database.get_db", fake_db),
            TestClient(app) as client,
            pytest.raises(WebSocketDisconnect) as exc,
            client.websocket_connect(f"/api/v1/ws/drivers/{_OTHER_COMPANY_ID}?token=tok") as ws,
        ):
            ws.receive_text()
        assert exc.value.code == 4001
        app.dependency_overrides.clear()

    def test_missing_token_rejected(self, app_and_db):
        app, db, user, driver, vr = app_and_db
        with (
            TestClient(app) as client,
            pytest.raises(WebSocketDisconnect) as exc,
            client.websocket_connect(f"/api/v1/ws/drivers/{_COMPANY_ID}") as ws,
        ):
            ws.receive_text()
        assert exc.value.code == 4001


class TestBroadcastThrottle:
    async def test_second_ping_within_throttle_window_is_skipped(self):
        old = live_dispatch.DRIVER_BROADCAST_THROTTLE_SECONDS
        live_dispatch.DRIVER_BROADCAST_THROTTLE_SECONDS = 3600
        broadcast = AsyncMock()
        driver = Driver(
            id=_DRIVER_ID,
            company_id=_COMPANY_ID,
            name="Jane",
            phone="+1500",
            status="on_route",
            current_lat=51.5,
            current_lon=-0.1,
        )
        try:
            with patch.object(live_manager, "broadcast", broadcast):
                await live_dispatch.broadcast_driver_location(driver, _COMPANY_ID)
                await live_dispatch.broadcast_driver_location(driver, _COMPANY_ID)
        finally:
            live_dispatch.DRIVER_BROADCAST_THROTTLE_SECONDS = old
        assert broadcast.await_count == 1

    async def test_no_fix_skips_broadcast(self):
        driver = Driver(id=_DRIVER_ID, company_id=_COMPANY_ID, name="Jane", phone="+1500", status="offline")
        broadcast = AsyncMock()
        with patch.object(live_manager, "broadcast", broadcast):
            await live_dispatch.broadcast_driver_location(driver, _COMPANY_ID)
        broadcast.assert_not_awaited()
