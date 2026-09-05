"""
Turn-by-turn directions service.

Fetches per-leg navigation steps (OSRM / ORS), caches them, and assembles
per-vehicle step lists for a finished optimization job. Fail-soft: a missing
or failing routing backend produces empty steps instead of breaking the job.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import get_settings
from app.services import cache

logger = structlog.get_logger(__name__)

_TIMEOUT = 10.0

HEAD_MODIFIERS = {"left", "right", "slight left", "slight right", "sharp left", "sharp right", "straight"}

OSRM_INSTRUCTIONS: dict[str, str] = {
    "depart": "Head {mod}",
    "turn": "Turn {mod}",
    "continue": "Continue {mod}",
    "new name": "Continue {mod}",
    "end of road": "Turn {mod} at the end of the road",
    "fork": "Keep {mod}",
    "merge": "Merge {mod}",
    "on ramp": "Take the ramp {mod}",
    "off ramp": "Take the exit {mod}",
    "roundabout": "In the roundabout take the {mod} exit",
    "rotary": "In the rotary take the {mod} exit",
    "roundabout turn": "At the roundabout turn {mod}",
    "exit roundabout": "Exit the roundabout",
    "exit rotary": "Exit the rotary",
    "uturn": "Make a U-turn",
    "arrive": "Arrive at your destination",
}


def _safe_modifier(modifier: str | None) -> str:
    return modifier if modifier in HEAD_MODIFIERS else "straight"


def build_osrm_instruction(step: dict[str, Any]) -> str:
    """Build a human-readable instruction string from an OSRM step."""
    maneuver = step.get("maneuver") or {}
    mtype = maneuver.get("type") or "continue"
    mod = _safe_modifier(maneuver.get("modifier"))
    name = (step.get("name") or "").strip()

    if mtype in ("roundabout", "rotary"):
        exit_idx = int(step.get("exits") or 0)
        if exit_idx:
            text = f"In the roundabout take exit {exit_idx}"
        else:
            text = OSRM_INSTRUCTIONS.get(mtype, "Continue {mod}").format(mod=mod)
    else:
        text = OSRM_INSTRUCTIONS.get(mtype, "Continue {mod}").format(mod=mod)

    if mtype in ("exit roundabout", "exit rotary", "uturn", "arrive"):
        base = text
    elif name:
        base = f"{text} onto {name}"
    else:
        base = text
    return base


def _normalize_osrm_step(step: dict[str, Any]) -> dict[str, Any]:
    maneuver = step.get("maneuver") or {}
    loc = maneuver.get("location")
    return {
        "instruction": build_osrm_instruction(step),
        "name": (step.get("name") or None),
        "distance_m": round(float(step.get("distance") or 0.0), 1),
        "duration_s": round(float(step.get("duration") or 0.0), 1),
        "maneuver": maneuver.get("type"),
        "modifier": maneuver.get("modifier"),
        "location": [loc[1], loc[0]] if loc else None,  # OSRM is [lon, lat]; expose [lat, lon]
    }


async def _fetch_osrm_leg(
    client: httpx.AsyncClient,
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> dict[str, Any] | None:
    settings = get_settings()
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    resp = await client.get(
        url,
        params={
            "steps": "true",
            "overview": "false",
            "geometries": "polyline6",
            "alternatives": "false",
            "annotations": "false",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    routes = data.get("routes") or []
    if data.get("code") != "Ok" or not routes:
        return None
    route = routes[0]
    steps: list[dict[str, Any]] = []
    for leg in route.get("legs") or []:
        for step in leg.get("steps") or []:
            steps.append(_normalize_osrm_step(step))
    return {
        "distance_m": round(float(route.get("distance") or 0.0), 1),
        "duration_s": round(float(route.get("duration") or 0.0), 1),
        "steps": steps,
    }


async def _fetch_ors_leg(
    client: httpx.AsyncClient,
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.ORS_API_KEY:
        return None
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    payload = {"coordinates": [[lon1, lat1], [lon2, lat2]]}
    headers = {
        "Authorization": settings.ORS_API_KEY,
        "Content-Type": "application/json",
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    features = data.get("features") or []
    if not features:
        return None
    props = features[0].get("properties") or {}
    segments = props.get("segments") or [{}]
    segment = segments[0]
    steps: list[dict[str, Any]] = []
    for step in segment.get("steps") or []:
        steps.append(
            {
                "instruction": step.get("instruction") or "Continue",
                "name": step.get("name") or None,
                "distance_m": round(float(step.get("distance") or 0.0), 1),
                "duration_s": round(float(step.get("duration") or 0.0), 1),
                "maneuver": step.get("type"),
                "modifier": None,
                "location": None,
            }
        )
    return {
        "distance_m": round(float(segment.get("distance") or 0.0), 1),
        "duration_s": round(float(segment.get("duration") or 0.0), 1),
        "steps": steps,
    }


async def fetch_route(
    backend: str,
    from_coord: tuple[float, float],
    to_coord: tuple[float, float],
) -> dict[str, Any] | None:
    """Fetch and cache turn-by-turn data for a single leg. Returns None on failure."""
    cached = cache.get_directions(backend, from_coord, to_coord)
    if cached is not None:
        return cached

    lon1, lat1 = from_coord[1], from_coord[0]
    lon2, lat2 = to_coord[1], to_coord[0]
    result = None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            if backend == "osrm":
                result = await _fetch_osrm_leg(client, lon1, lat1, lon2, lat2)
            elif backend == "ors":
                result = await _fetch_ors_leg(client, lon1, lat1, lon2, lat2)
    except Exception as exc:
        logger.warning("directions_leg_failed", backend=backend, error=str(exc))
    if result is not None:
        cache.set_directions(backend, from_coord, to_coord, result)
    return result


async def build_direction_leg(
    backend: str,
    from_wp: dict[str, Any],
    to_wp: dict[str, Any],
    from_label: str | None,
    to_label: str | None,
) -> dict[str, Any]:
    """Assemble a single leg entry, fetching (or falling back for) the step data."""
    from_coord = (from_wp["lat"], from_wp["lon"])
    to_coord = (to_wp["lat"], to_wp["lon"])

    leg_data: dict[str, Any] | None = None
    if backend in ("osrm", "ors"):
        leg_data = await fetch_route(backend, from_coord, to_coord)

    steps = leg_data.get("steps", []) if leg_data else []
    return {
        "from_stop": {
            "id": from_wp.get("id"),
            "label": from_label,
            "lat": from_wp["lat"],
            "lon": from_wp["lon"],
        },
        "to_stop": {
            "id": to_wp.get("id"),
            "label": to_label,
            "lat": to_wp["lat"],
            "lon": to_wp["lon"],
        },
        "distance_km": round(leg_data["distance_m"] / 1000.0, 3) if leg_data else None,
        "duration_s": leg_data["duration_s"] if leg_data else None,
        "steps": steps,
    }


async def build_vehicle_directions(
    backend: str,
    vehicle: dict[str, Any],
    labels: list[str | None],
) -> dict[str, Any]:
    """Compute the per-leg step list for one vehicle route."""
    waypoints = vehicle.get("waypoints") or []
    legs: list[dict[str, Any]] = []
    for i in range(len(waypoints) - 1):
        legs.append(
            await build_direction_leg(
                backend,
                waypoints[i],
                waypoints[i + 1],
                labels[i] if labels else None,
                labels[i + 1] if labels else None,
            )
        )
    return {"vehicle_id": vehicle.get("vehicle_id"), "legs": legs}
