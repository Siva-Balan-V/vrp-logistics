"""
Live ETA recalculation for driver routes.
Uses haversine with road factor as fallback; optionally queries OSRM/ORS for point-to-point accuracy.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import get_settings
from app.services.distance_matrix import haversine_km

logger = structlog.get_logger(__name__)

ROAD_FACTOR = 1.35
SPEED_KMH = 30.0


async def _osrm_route_time(lat1: float, lon1: float, lat2: float, lon2: float) -> float | None:
    """Query OSRM route endpoint for point-to-point duration in minutes."""
    settings = get_settings()
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params={"overview": "false"})
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                return data["routes"][0]["duration"] / 60
    except Exception as e:
        logger.warning("osrm_route_failed", error=str(e))
    return None


async def _ors_route_time(lat1: float, lon1: float, lat2: float, lon2: float) -> float | None:
    """Query ORS directions endpoint for point-to-point duration in minutes."""
    settings = get_settings()
    if not settings.ORS_API_KEY:
        return None
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={"coordinates": [[lon1, lat1], [lon2, lat2]]},
                headers={
                    "Authorization": settings.ORS_API_KEY,
                    "Content-Type": "application/json",
                },
            )
            data = resp.json()
            if data.get("features"):
                duration = data["features"][0]["properties"]["segments"][0]["duration"]
                return duration / 60
    except Exception as e:
        logger.warning("ors_route_failed", error=str(e))
    return None


async def _point_to_point_minutes(
    lat1: float, lon1: float, lat2: float, lon2: float, backend: str = "haversine"
) -> float:
    """Get travel time (minutes) between two points using the preferred backend."""
    if backend == "osrm":
        t = await _osrm_route_time(lat1, lon1, lat2, lon2)
        if t is not None:
            return t
    elif backend == "ors":
        t = await _ors_route_time(lat1, lon1, lat2, lon2)
        if t is not None:
            return t

    d = haversine_km(lat1, lon1, lat2, lon2) * ROAD_FACTOR
    return (d / SPEED_KMH) * 60


def _find_next_stop(driver_lat: float, driver_lon: float, waypoints: list[dict]) -> int:
    """Find the index of the next unvisited waypoint."""
    visited_threshold_km = 0.2

    last_visited = -1
    for i, wp in enumerate(waypoints):
        d = haversine_km(driver_lat, driver_lon, wp["lat"], wp["lon"])
        if d < visited_threshold_km:
            last_visited = i

    next_stop = last_visited + 1
    if next_stop >= len(waypoints):
        next_stop = len(waypoints) - 1
    return max(next_stop, 1)  # at least past the start depot


async def compute_live_eta(
    driver_lat: float,
    driver_lon: float,
    waypoints: list[dict],
    arrival_times: list[int] | None = None,
    labels: list[str | None] | None = None,
    backend: str = "haversine",
) -> dict[str, Any]:
    """
    Recalculate ETAs from the driver's current position forward.

    Returns:
    {
      "current_position": {"lat": ..., "lon": ...},
      "remaining_stops": [{stop_index, id, label, original_eta_min, live_eta_min, delta_min}],
      "total_remaining_distance_km": float,
      "total_remaining_time_min": float,
      "next_stop_index": int,
    }
    """
    if not waypoints or len(waypoints) < 2:
        return {
            "current_position": {"lat": driver_lat, "lon": driver_lon},
            "remaining_stops": [],
            "total_remaining_distance_km": 0,
            "total_remaining_time_min": 0,
            "next_stop_index": -1,
        }

    next_idx = _find_next_stop(driver_lat, driver_lon, waypoints)

    remaining_stops = []
    total_dist_km = 0.0
    prev_lat, prev_lon = driver_lat, driver_lon

    for i in range(next_idx, len(waypoints)):
        wp = waypoints[i]
        seg_min = await _point_to_point_minutes(prev_lat, prev_lon, wp["lat"], wp["lon"], backend)
        seg_km = haversine_km(prev_lat, prev_lon, wp["lat"], wp["lon"]) * ROAD_FACTOR
        total_dist_km += seg_km

        original_min = (arrival_times[i] / 60) if arrival_times and i < len(arrival_times) else None
        live_eta_min = round(seg_min + (remaining_stops[-1]["live_eta_min"] if remaining_stops else 0), 1)

        remaining_stops.append(
            {
                "stop_index": i,
                "id": wp.get("id"),
                "label": (labels[i] if labels and i < len(labels) else None) or wp.get("label"),
                "original_eta_min": original_min,
                "live_eta_min": live_eta_min,
                "delta_min": round(live_eta_min - original_min, 1) if original_min is not None else None,
            }
        )

        prev_lat, prev_lon = wp["lat"], wp["lon"]

    return {
        "current_position": {"lat": driver_lat, "lon": driver_lon},
        "remaining_stops": remaining_stops,
        "total_remaining_distance_km": round(total_dist_km, 2),
        "total_remaining_time_min": round(remaining_stops[-1]["live_eta_min"] if remaining_stops else 0, 1),
        "next_stop_index": next_idx,
    }
