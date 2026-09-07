"""Tests for the stop lifecycle state machine and dispatch notifications."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.db import Driver, NotificationConfig, NotificationLog
from app.services import cache
from app.services.notifications import send_notification
from app.services.stop_lifecycle import (
    InvalidStopTransitionError,
    StopNotFoundError,
    can_transition,
    find_waypoint,
    notify_stop_event,
    persist_stop_status,
    set_stop_status,
    should_notify_delayed,
)

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DRIVER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
_JOB_ID = uuid.UUID("00000000-0000-0000-0000-00000000000a")


def _route_dict(status_overrides: dict[int, str] | None = None) -> dict:
    status_overrides = status_overrides or {}
    waypoints = []
    for wp_id, lat, lon in [(0, 51.5074, -0.1278), (1, 51.51, -0.12), (2, 51.52, -0.13), (0, 51.5074, -0.1278)]:
        waypoints.append(
            {"id": wp_id, "lat": lat, "lon": lon, "priority": 1, "status": status_overrides.get(wp_id, "pending")}
        )
    return {
        "vehicle_id": 1,
        "route": [0, 1, 2, 0],
        "route_labels": ["Depot", "Stop 1", "Stop 2", "Depot"],
        "distance_km": 45.0,
        "time_minutes": 90.0,
        "packages_delivered": 2,
        "waypoints": waypoints,
        "arrival_times": [0, 1800, 3600],
    }


def _make_driver(current_lat=None, current_lon=None) -> Driver:
    return Driver(
        id=_DRIVER_ID,
        company_id=_COMPANY_ID,
        name="Jane",
        phone="+15551234567",
        status="on_route",
        current_lat=current_lat,
        current_lon=current_lon,
    )


@pytest.fixture(autouse=True)
def clear_cache():
    cache._job_cache.clear()
    yield
    cache._job_cache.clear()


class TestCanTransition:
    def test_forward_progression_allowed(self):
        assert can_transition("pending", "en_route")
        assert can_transition("en_route", "arrived")
        assert can_transition("arrived", "delivered")

    def test_out_of_order_rejected(self):
        assert not can_transition("pending", "arrived")
        assert not can_transition("pending", "delivered")
        assert not can_transition("en_route", "delivered")
        assert not can_transition("arrived", "en_route")
        assert not can_transition("delivered", "pending")

    def test_same_status_is_idempotent(self):
        assert can_transition("pending", "pending")
        assert can_transition("delivered", "delivered")

    def test_unknown_statuses_rejected(self):
        assert not can_transition("pending", "shipped")
        assert can_transition("pending", "pending")


class TestSetStopStatus:
    def test_mutates_waypoint_and_returns_it(self):
        route = _route_dict()
        wp = set_stop_status(route, 1, "en_route")
        assert wp["status"] == "en_route"
        assert find_waypoint(route, 1)["status"] == "en_route"

    def test_out_of_order_raises_with_context(self):
        route = _route_dict({1: "arrived"})
        with pytest.raises(InvalidStopTransitionError) as exc:
            set_stop_status(route, 1, "pending", validate=True)
        assert exc.value.current == "arrived"
        assert exc.value.requested == "pending"

    def test_missing_stop_raises(self):
        with pytest.raises(StopNotFoundError):
            set_stop_status(_route_dict(), 99, "en_route")

    def test_legacy_waypoint_without_status_defaults_to_pending(self):
        waypoints = [{"id": 1, "lat": 51.51, "lon": -0.12, "priority": 1}]
        route = {"waypoints": waypoints, "vehicle_id": 1}
        set_stop_status(route, 1, "en_route")
        assert waypoints[0]["status"] == "en_route"

    def test_unknown_status_value_rejected(self):
        with pytest.raises(ValueError):
            set_stop_status(_route_dict(), 1, "shipped")

    def test_validate_false_force_sets_any_status(self):
        route = _route_dict({1: "arrived"})
        set_stop_status(route, 1, "pending", validate=False)
        assert find_waypoint(route, 1)["status"] == "pending"

    def test_delivered_is_terminal(self):
        route = _route_dict({1: "delivered"})
        with pytest.raises(InvalidStopTransitionError):
            set_stop_status(route, 1, "arrived", validate=True)


class TestShouldNotifyDelayed:
    def _eta(self, deltas):
        return {"remaining_stops": [{"id": i, "delta_min": d} for i, d in enumerate(deltas)]}

    def test_detects_delay_over_threshold(self):
        assert should_notify_delayed(self._eta([5.0, 20.0]), 15.0)

    def test_on_time_within_threshold(self):
        assert not should_notify_delayed(self._eta([5.0, 10.0]), 15.0)

    def test_missing_original_eta_never_delayed(self):
        assert not should_notify_delayed(self._eta([None, None]), 15.0)

    def test_no_remaining_stops(self):
        assert not should_notify_delayed({"remaining_stops": []}, 15.0)


class TestNotifyStopEvent:
    @pytest.fixture
    def db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    async def test_arrived_emits_arrived_trigger(self, db):
        driver = _make_driver()
        send = AsyncMock(return_value=[{"channel": "sms"}])
        with patch("app.services.stop_lifecycle.send_notification", send):
            triggered = await notify_stop_event(
                db=db,
                company_id=_COMPANY_ID,
                driver_id=_DRIVER_ID,
                driver=driver,
                route=_route_dict(),
                new_status="arrived",
            )
        assert triggered == [{"channel": "sms"}]
        send.assert_awaited_once()
        assert send.call_args.args[3] == "arrived"

    async def test_en_route_without_position_emits_nothing(self, db):
        driver = _make_driver()  # no GPS fix yet
        send = AsyncMock(return_value=[])
        with patch("app.services.stop_lifecycle.send_notification", send):
            triggered = await notify_stop_event(
                db=db,
                company_id=_COMPANY_ID,
                driver_id=_DRIVER_ID,
                driver=driver,
                route=_route_dict(),
                new_status="en_route",
            )
        assert triggered == []
        send.assert_not_awaited()


class TestNotifyStopEventDelayedViaEta:
    async def test_emits_delayed_when_late(self):
        driver = _make_driver(current_lat=51.5070, current_lon=-0.1280)
        eta = {"remaining_stops": [{"id": 2, "delta_min": 25.0}]}
        send = AsyncMock(return_value=[{"channel": "sms"}])
        with (
            patch("app.services.stop_lifecycle.send_notification", send) as _send,
            patch("app.services.stop_lifecycle.compute_live_eta", AsyncMock(return_value=eta)) as compute,
        ):
            triggered = await notify_stop_event(
                db=AsyncMock(),
                company_id=_COMPANY_ID,
                driver_id=_DRIVER_ID,
                driver=driver,
                route=_route_dict(),
                new_status="arrived",
                threshold_min=15.0,
            )
        triggers = [call.args[3] for call in send.await_args_list]
        assert triggers == ["arrived", "delayed"]
        assert len(triggered) == 2
        compute.assert_awaited_once()

    async def test_skips_delayed_when_on_time(self):
        driver = _make_driver(current_lat=51.5070, current_lon=-0.1280)
        eta = {"remaining_stops": [{"id": 2, "delta_min": 3.0}]}
        with (
            patch(
                "app.services.stop_lifecycle.send_notification", AsyncMock(return_value=[{"channel": "sms"}])
            ) as send,
            patch("app.services.stop_lifecycle.compute_live_eta", AsyncMock(return_value=eta)),
        ):
            await notify_stop_event(
                db=AsyncMock(),
                company_id=_COMPANY_ID,
                driver_id=_DRIVER_ID,
                driver=driver,
                route=_route_dict(),
                new_status="arrived",
                threshold_min=15.0,
            )
        triggers = [call.args[3] for call in send.await_args_list]
        assert triggers == ["arrived"]


class TestPersistStopStatus:
    async def test_updates_cached_job_result(self):
        resp = {
            "job_id": str(_JOB_ID),
            "status": "success",
            "total_locations": 2,
            "assigned_count": 2,
            "unassigned_count": 0,
            "vehicles_used": 1,
            "total_distance_km": 45.0,
            "total_time_minutes": 90.0,
            "vehicles": [_route_dict()],
            "unassigned": [],
            "unassigned_labels": [],
            "matrix_source": "haversine",
        }
        cache.set_job(_COMPANY_ID, str(_JOB_ID), resp)

        db = AsyncMock()

        async def _execute(_stmt):
            out = MagicMock()
            out.scalar_one_or_none.return_value = None
            return out

        db.execute.side_effect = _execute
        await persist_stop_status(db, _COMPANY_ID, str(_JOB_ID), 1, 1, "arrived")

        cached = cache.get_job(_COMPANY_ID, str(_JOB_ID))
        assert cached["vehicles"][0]["waypoints"][1]["status"] == "arrived"
        assert cached["vehicles"][0]["waypoints"][2]["status"] == "pending"

    async def test_updates_db_route_and_response_when_present(self):
        job = MagicMock()
        job.response_json = {"vehicles": [_route_dict()]}
        vr = MagicMock()
        vr.route_json = _route_dict()

        async def _execute(stmt):
            out = MagicMock()
            if "FROM optimization_jobs" in str(stmt):
                out.scalar_one_or_none.return_value = job
            else:
                out.scalar_one_or_none.return_value = vr
            return out

        db = AsyncMock()
        db.execute.side_effect = _execute

        await persist_stop_status(db, _COMPANY_ID, str(_JOB_ID), 1, 2, "en_route")

        assert vr.route_json["waypoints"][2]["status"] == "en_route"
        assert job.response_json["vehicles"][0]["waypoints"][2]["status"] == "en_route"
        db.flush.assert_awaited_once()

    async def test_invalid_job_uuid_is_noop(self):
        await persist_stop_status(AsyncMock(), _COMPANY_ID, "not-a-uuid", 1, 1, "arrived")


class TestSendNotificationPipeline:
    """Verify the arrived trigger flows through the real producer with a mocked provider."""

    @pytest.fixture
    def db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    async def test_arrived_trigger_sends_via_mocked_provider_and_logs(self, db):
        ncfg = NotificationConfig(
            company_id=_COMPANY_ID,
            sms_enabled=True,
            email_enabled=False,
            triggers=["out_for_delivery", "arrived", "delayed"],
        )

        async def _execute(stmt):
            out = MagicMock()
            if "FROM notification_config" in str(stmt):
                out.scalar_one_or_none.return_value = ncfg
            else:  # Driver lookup for the message
                out.scalar_one_or_none.return_value = _make_driver()
            return out

        db.execute.side_effect = _execute

        sms = AsyncMock()
        sms.send = AsyncMock(return_value=True)
        with (
            patch("app.services.notifications._get_sms_provider", return_value=sms),
            patch("app.services.notifications._get_email_provider") as email_provider,
        ):
            sent = await send_notification(db, _COMPANY_ID, _DRIVER_ID, "arrived", customer_phone="+15005551234")

        assert sent == [{"channel": "sms", "recipient": "+15005551234", "status": "sent"}]
        sms.send.assert_awaited_once()
        email_provider.assert_not_called()
        added_logs = [c.args[0] for c in db.add.call_args_list]
        assert any(
            isinstance(log, NotificationLog) and log.trigger == "arrived" and log.channel == "sms" for log in added_logs
        )
        db.flush.assert_awaited_once()

    async def test_disabled_trigger_is_skipped(self, db):
        ncfg = NotificationConfig(
            company_id=_COMPANY_ID,
            sms_enabled=True,
            triggers=["out_for_delivery"],
        )
        db.execute.side_effect = _execute_not_found_or(ncfg)
        with patch("app.services.notifications._get_sms_provider") as sms:
            sent = await send_notification(db, _COMPANY_ID, _DRIVER_ID, "arrived", customer_phone="+15005551234")
        assert sent == []
        sms.assert_not_called()


def _execute_not_found_or(value):
    async def _execute(stmt):
        out = MagicMock()
        out.scalar_one_or_none.return_value = value
        return out

    return _execute
