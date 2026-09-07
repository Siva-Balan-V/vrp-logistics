"""
Stop lifecycle state machine and automated dispatch notifications.

A stop progresses linearly: pending → en_route → arrived → delivered.
Transitions are guarded against out-of-order updates, persisted to the job
result (in-memory cache + PostgreSQL when available), and emit notification
triggers (`arrived`, and `delayed` when the live-ETA delta exceeds the
configured threshold from eta.py).
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import OptimizationJob, VehicleRoute
from app.services import cache
from app.services.eta import compute_live_eta
from app.services.notifications import send_notification

logger = structlog.get_logger(__name__)

VALID_STATUSES = ("pending", "en_route", "arrived", "delivered")

# Forward-only progression. Same-status updates are treated as idempotent no-ops.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"en_route"},
    "en_route": {"arrived"},
    "arrived": {"delivered"},
    "delivered": set(),
}


class StopNotFoundError(Exception):
    """Requested stop is not part of the driver's assigned route."""


class InvalidStopTransitionError(Exception):
    def __init__(self, current: str, requested: str):
        super().__init__(f"Cannot transition stop from {current!r} to {requested!r}")
        self.current = current
        self.requested = requested


def can_transition(current: str, requested: str) -> bool:
    """Validate a stop status transition (forward-only, idempotent on same status)."""
    if current == requested:
        return True
    return requested in ALLOWED_TRANSITIONS.get(current, set())


def find_waypoint(route: dict, stop_id: int) -> dict | None:
    return next((wp for wp in route.get("waypoints", []) if wp.get("id") == stop_id), None)


def set_stop_status(route: dict, stop_id: int, new_status: str, validate: bool = True) -> dict:
    """
    Set a stop's status on a route dict.

    Returns the mutated waypoint. Raises StopNotFoundError if the stop is absent.
    When validate=True, raises InvalidStopTransitionError on out-of-order updates.
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Unknown stop status: {new_status!r}")

    wp = find_waypoint(route, stop_id)
    if wp is None:
        raise StopNotFoundError(stop_id)

    current = wp.get("status", "pending")  # legacy routes default to pending
    if validate and not can_transition(current, new_status):
        raise InvalidStopTransitionError(current, new_status)

    wp["status"] = new_status
    return wp


def should_notify_delayed(eta_result: dict, threshold_min: float) -> bool:
    """True when any remaining stop's live-ETA delta exceeds the delay threshold."""
    stops = eta_result.get("remaining_stops", [])
    return any(stop.get("delta_min") is not None and stop["delta_min"] > threshold_min for stop in stops)


async def persist_stop_status(
    db: AsyncSession | None,
    company_id: uuid.UUID,
    job_id: str,
    vehicle_id: int,
    stop_id: int,
    new_status: str,
) -> None:
    """
    Persist a stop status transition to PostgreSQL (route_json + response_json)
    and to the in-memory job cache. Both stores are updated as best-effort; a
    stale/missing row never fails the request.
    """
    resp = cache.get_job(company_id, job_id)
    if resp is not None:
        for vehicle in resp.get("vehicles", []):
            if vehicle.get("vehicle_id") == vehicle_id:
                set_stop_status(vehicle, stop_id, new_status, validate=False)
        cache.set_job(company_id, job_id, resp)

    if db is None:
        return
    try:
        job_uuid = uuid.UUID(job_id)
    except (ValueError, TypeError):
        return

    try:
        res = await db.execute(
            select(VehicleRoute).where(
                VehicleRoute.job_id == job_uuid,
                VehicleRoute.vehicle_id == vehicle_id,
            )
        )
        vr = res.scalar_one_or_none()
        if vr is not None and vr.route_json:
            set_stop_status(vr.route_json, stop_id, new_status, validate=False)
            vr.route_json = vr.route_json

        res = await db.execute(
            select(OptimizationJob).where(
                OptimizationJob.job_id == job_uuid,
                OptimizationJob.company_id == company_id,
            )
        )
        job = res.scalar_one_or_none()
        if job is not None and job.response_json:
            for vehicle in job.response_json.get("vehicles", []):
                if vehicle.get("vehicle_id") == vehicle_id:
                    set_stop_status(vehicle, stop_id, new_status, validate=False)
            job.response_json = job.response_json

        await db.flush()
    except Exception:
        logger.exception("stop_status_persist_failed", job_id=job_id, stop_id=stop_id)


async def notify_stop_event(
    db: AsyncSession,
    company_id: uuid.UUID,
    driver_id: uuid.UUID,
    driver: Any,
    route: dict,
    new_status: str,
    backend: str = "haversine",
    threshold_min: float = 15.0,
) -> list[dict]:
    """
    Emit automated notification triggers for a stop status transition.

    - `arrived` is emitted when a stop is marked arrived.
    - `delayed` is emitted (in addition) when the driver has a live position
      and any remaining stop's live-ETA delta exceeds threshold_min.
    Returns the notifications that were sent (channel/status entries).
    """
    triggered: list[dict] = []

    if new_status == "arrived":
        sent = await send_notification(db, company_id, driver_id, "arrived")
        triggered.extend(sent)
        logger.info("stop_notification_triggered", trigger="arrived", driver_id=str(driver_id))

    if new_status in ("en_route", "arrived") and driver is not None and driver.current_lat is not None:
        try:
            eta = await compute_live_eta(
                driver_lat=driver.current_lat,
                driver_lon=driver.current_lon,
                waypoints=route.get("waypoints", []),
                arrival_times=route.get("arrival_times") or None,
                labels=route.get("route_labels"),
                backend=backend,
            )
        except Exception:
            logger.exception("live_eta_compute_failed", driver_id=str(driver_id))
            eta = None
        if eta is not None and should_notify_delayed(eta, threshold_min):
            sent = await send_notification(db, company_id, driver_id, "delayed")
            triggered.extend(sent)
            logger.info("stop_notification_triggered", trigger="delayed", driver_id=str(driver_id))

    return triggered
