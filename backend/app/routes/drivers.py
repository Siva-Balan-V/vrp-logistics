"""
Driver management and GPS tracking routes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_user
from app.models.db import Driver, User, VehicleRoute
from app.models.schemas import (
    DriverAssignment,
    DriverCreate,
    DriverLocationUpdate,
    StopStatusUpdate,
)
from app.services.eta import compute_live_eta
from app.services.live_dispatch import broadcast_driver_location
from app.services.notifications import send_notification
from app.services.stop_lifecycle import (
    InvalidStopTransitionError,
    find_waypoint,
    notify_stop_event,
    persist_stop_status,
    set_stop_status,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/drivers", tags=["drivers"])


def _driver_to_response(d: Driver, route: dict | None = None) -> dict:
    return {
        "id": str(d.id),
        "name": d.name,
        "phone": d.phone,
        "status": d.status,
        "current_lat": d.current_lat,
        "current_lon": d.current_lon,
        "last_ping_at": d.last_ping_at.isoformat() if d.last_ping_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "assigned_route": route,
    }


async def _get_assigned_route(db: AsyncSession, driver_id: uuid.UUID) -> dict | None:
    """Fetch the most recent assigned route for a driver."""
    result = await db.execute(
        select(VehicleRoute).where(VehicleRoute.driver_id == driver_id).order_by(desc(VehicleRoute.created_at)).limit(1)
    )
    vr = result.scalar_one_or_none()
    if not vr:
        return None
    return {
        "job_id": str(vr.job_id),
        "vehicle_id": vr.vehicle_id,
        "distance_km": vr.distance_km,
        "time_minutes": vr.time_minutes,
        "packages": vr.packages,
        "route": vr.route_json,
    }


@router.get("")
async def list_drivers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> list[dict]:
    """List all drivers for the current company."""
    result = await db.execute(
        select(Driver).where(Driver.company_id == user.company_id).order_by(Driver.created_at.desc())
    )
    drivers = result.scalars().all()
    return [_driver_to_response(d) for d in drivers]


@router.post("", status_code=201)
async def create_driver(
    body: DriverCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """Register a new driver."""
    driver = Driver(
        company_id=user.company_id,
        name=body.name,
        phone=body.phone,
        status="offline",
    )
    db.add(driver)
    await db.flush()
    logger.info("driver_created", driver_id=str(driver.id))
    return _driver_to_response(driver)


@router.get("/{driver_id}")
async def get_driver(
    driver_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """Get driver detail including today's assigned route."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id, Driver.company_id == user.company_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")
    route = await _get_assigned_route(db, driver_id)
    return _driver_to_response(driver, route)


@router.patch("/{driver_id}/location")
async def update_driver_location(
    driver_id: uuid.UUID,
    body: DriverLocationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """GPS ping — update driver position and status."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id, Driver.company_id == user.company_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    now = datetime.now(UTC)
    driver.current_lat = body.lat
    driver.current_lon = body.lon
    driver.last_ping_at = now
    if driver.status == "active":
        driver.status = "on_route"
    elif driver.status == "offline":
        driver.status = "active"

    await db.flush()
    route = await _get_assigned_route(db, driver_id)
    try:
        await broadcast_driver_location(
            driver,
            user.company_id,
            route.get("route") if route else None,
        )
    except Exception:
        logger.exception("driver_location_broadcast_failed", driver_id=str(driver_id))
    return _driver_to_response(driver, route)


@router.post("/{driver_id}/assign")
async def assign_driver_route(
    driver_id: uuid.UUID,
    body: DriverAssignment,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """Assign a driver to a vehicle route from a completed job."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id, Driver.company_id == user.company_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    result = await db.execute(
        select(VehicleRoute).where(
            VehicleRoute.job_id == uuid.UUID(body.job_id),
            VehicleRoute.vehicle_id == body.vehicle_id,
        )
    )
    vr = result.scalar_one_or_none()
    if not vr:
        raise HTTPException(404, "Vehicle route not found")

    vr.driver_id = driver_id
    driver.status = "active"
    await db.flush()
    logger.info("driver_assigned", driver_id=str(driver_id), job_id=body.job_id)

    try:
        await send_notification(db, user.company_id, driver_id, "out_for_delivery")
    except Exception:
        logger.exception("notification_trigger_failed", trigger="out_for_delivery")

    route = await _get_assigned_route(db, driver_id)
    return _driver_to_response(driver, route)


@router.get("/{driver_id}/eta")
async def get_driver_eta(
    driver_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """Get live ETA estimates for a driver's remaining stops."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id, Driver.company_id == user.company_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    route = await _get_assigned_route(db, driver_id)
    if not route or not driver.current_lat:
        return {"remaining_stops": [], "total_remaining_time_min": 0}

    route_data = route.get("route", {})
    waypoints = route_data.get("waypoints", [])
    arrival_times = route_data.get("arrival_times", [])
    labels = route_data.get("route_labels", [])

    cfg = get_settings()
    eta = await compute_live_eta(
        driver_lat=driver.current_lat,
        driver_lon=driver.current_lon,
        waypoints=waypoints,
        arrival_times=arrival_times,
        labels=labels,
        backend=cfg.ROUTING_BACKEND,
    )
    return eta


@router.post("/{driver_id}/stops/{stop_id}/status")
async def update_stop_status(
    driver_id: uuid.UUID,
    stop_id: int,
    body: StopStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """Advance a stop through its lifecycle (pending → en_route → arrived → delivered)."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id, Driver.company_id == user.company_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    route = await _get_assigned_route(db, driver_id)
    if not route:
        raise HTTPException(404, "No route assigned")

    route_data = route.get("route", {})
    waypoint = find_waypoint(route_data, stop_id)
    if waypoint is None:
        raise HTTPException(404, "Stop not found on assigned route")
    previous_status = waypoint.get("status", "pending")
    try:
        set_stop_status(route_data, stop_id, body.status, validate=True)
    except InvalidStopTransitionError as exc:
        raise HTTPException(409, f"Invalid transition from {exc.current} to {exc.requested}") from exc

    await persist_stop_status(db, user.company_id, route["job_id"], route["vehicle_id"], stop_id, body.status)

    cfg = get_settings()
    triggered = await notify_stop_event(
        db=db,
        company_id=user.company_id,
        driver_id=driver_id,
        driver=driver,
        route=route_data,
        new_status=body.status,
        backend=cfg.ROUTING_BACKEND,
        threshold_min=cfg.NOTIFY_DELAY_THRESHOLD_MIN,
    )
    logger.info("stop_status_updated", driver_id=str(driver_id), stop_id=stop_id, status=body.status)

    return {
        "driver_id": str(driver_id),
        "job_id": route["job_id"],
        "vehicle_id": route["vehicle_id"],
        "stop_id": stop_id,
        "previous_status": previous_status,
        "status": body.status,
        "notifications": triggered,
    }
