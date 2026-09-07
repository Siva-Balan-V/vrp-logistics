"""
Live fleet dispatch: broadcast driver position updates over WebSocket.

Each company subscribes to `WS /api/v1/ws/drivers/{company_id}`; the GPS ping
route fans out a lightweight `driver.update` payload (throttled to 1/s per
driver) with best-effort haversine ETAs so the dispatch map stays live without
blocking on external routers.
"""

from __future__ import annotations

import time

import structlog

from app.services.eta import compute_live_eta
from app.websocket_manager import live_manager

logger = structlog.get_logger(__name__)

DRIVER_BROADCAST_THROTTLE_SECONDS = 1.0
_last_broadcast_ts: dict[str, float] = {}


def _throttle_ok(driver_id: str, now: float) -> bool:
    last = _last_broadcast_ts.get(driver_id)
    if last is not None and now - last < DRIVER_BROADCAST_THROTTLE_SECONDS:
        return False
    _last_broadcast_ts[driver_id] = now
    return True


async def _eta_payload(driver, route: dict | None) -> dict | None:
    """Best-effort live ETA (haversine, offline-safe) for the driver's route."""
    try:
        if not route or driver.current_lat is None:
            return None
        waypoints = route.get("waypoints", [])
        if len(waypoints) < 2:
            return None
        eta = await compute_live_eta(
            driver_lat=driver.current_lat,
            driver_lon=driver.current_lon,
            waypoints=waypoints,
            arrival_times=route.get("arrival_times") or None,
            labels=route.get("route_labels"),
            backend="haversine",
        )
        return {
            "total_remaining_time_min": eta["total_remaining_time_min"],
            "total_remaining_distance_km": eta["total_remaining_distance_km"],
            "remaining_stops": [
                {
                    "id": s["id"],
                    "label": s["label"],
                    "original_eta_min": s["original_eta_min"],
                    "live_eta_min": s["live_eta_min"],
                    "delta_min": s["delta_min"],
                }
                for s in eta["remaining_stops"]
            ],
        }
    except Exception:
        logger.exception("live_eta_payload_failed", driver_id=str(driver.id))
        return None


async def broadcast_driver_location(driver, company_id, route: dict | None = None) -> bool:
    """
    Publish a driver position update to the company's dispatch channel.

    Returns True when a broadcast was sent, False when it was throttled or the
    driver has no fix yet.
    """
    if driver.current_lat is None:
        return False
    if not _throttle_ok(str(driver.id), time.monotonic()):
        return False

    payload = {
        "type": "driver.update",
        "company_id": str(company_id),
        "driver_id": str(driver.id),
        "name": driver.name,
        "status": driver.status,
        "lat": driver.current_lat,
        "lon": driver.current_lon,
        "last_ping_at": driver.last_ping_at.isoformat() if driver.last_ping_at else None,
        "eta": await _eta_payload(driver, route),
    }
    logger.info("driver_location_broadcast", company_id=str(company_id), driver_id=str(driver.id))
    await live_manager.broadcast(str(company_id), payload)
    return True
