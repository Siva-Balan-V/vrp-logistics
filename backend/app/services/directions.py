"""
Turn-by-turn directions service.

Generates step-by-step driving instructions between consecutive stops using the
same routing backend that produced the distance matrix:

  - OSRM        → `/route/v1/driving` with `steps=true` (public or self-hosted)
  - ORS         → `/v2/directions/driving-car` with API key
  - Haversine   → single "proceed to waypoint" step fallback (no API needed)

Each leg is cached by (backend, origin, dest). A per-leg result carries the
maneuver steps plus the full driving geometry as a [[lon, lat], ...] polyline.
"""

from __future__ import annotations

import asyncio

import httpx
import structlog

from app.config import get_settings
from app.models.schemas import DirectionStep
from app.services import cache
from app.services.distance_matrix import haversine_km

logger = structlog.get_logger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# OSRM
# ─────────────────────────────────────────────────────────────────────────────


def _osrm_instruction(step: dict) -> str:
    """Build a human-readable instruction from an OSRM step."""
    man = step.get("maneuver") or {}
    mtype = man.get("type") or ""
    modifier = man.get("modifier") or ""
    name = (step.get("name") or "").strip()

    if mtype in ("depart", "arrive"):
        return f"{mtype.capitalize()} {name}".strip() if name else mtype.capitalize()

    if modifier and name:
        return f"{modifier} onto {name}"
    if name:
        return f"Follow {name}"
    if modifier:
        return f"Turn {modifier}"
    return "Continue"


async def _osrm_leg(client: httpx.AsyncClient, origin, dest, base_url: str) -> tuple[list[dict], list[list[float]]]:
    """Call OSRM /route and return (raw steps, polyline coordinates)."""
    coord_str = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
    url = (
        f"{base_url}/route/v1/driving/{coord_str}"
        "?overview=full&geometries=geojson&steps=true&annotations=duration,distance"
    )
    resp = await client.get(url, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"OSRM route error: code={data.get('code')}")
    route = data["routes"][0]

    steps = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            man = step.get("maneuver") or {}
            location = man.get("location") or ([origin[1], origin[0]] if steps else [dest[1], dest[0]])
            steps.append(
                {
                    "instruction": _osrm_instruction(step),
                    "distance_m": float(step.get("distance", 0.0)),
                    "duration_s": float(step.get("duration", 0.0)),
                    "lon": float(location[0]),
                    "lat": float(location[1]),
                    "maneuver": man.get("type") or None,
                }
            )
    geometry = (route.get("geometry") or {}).get("coordinates") or []
    return steps, geometry


# ─────────────────────────────────────────────────────────────────────────────
# ORS
# ─────────────────────────────────────────────────────────────────────────────


async def _ors_leg(client: httpx.AsyncClient, origin, dest, api_key: str) -> tuple[list[dict], list[list[float]]]:
    """Call ORS /v2/directions and return (raw steps, polyline coordinates)."""
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key}
    params = {
        "start": f"{origin[1]},{origin[0]}",
        "end": f"{dest[1]},{dest[0]}",
        "steps": "true",
        "geometry_format": "geojson",
    }
    resp = await client.get(url, params=params, headers=headers, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    routes = data.get("routes")
    if not routes:
        raise ValueError("ORS route error: no routes returned")
    route = routes[0]

    steps = []
    for segment in route.get("segments", []):
        for step in segment.get("steps", []):
            location = step.get("start_location")
            if not location or len(location) != 2:
                location = [origin[1], origin[0]] if not steps else [dest[1], dest[0]]
            steps.append(
                {
                    "instruction": step.get("instruction") or "",
                    "distance_m": float(step.get("distance", 0.0)),
                    "duration_s": float(step.get("duration", 0.0)),
                    "lon": float(location[0]),
                    "lat": float(location[1]),
                    "maneuver": step.get("type"),
                }
            )
    geometry = (route.get("geometry") or {}).get("coordinates") or []
    return steps, geometry


# ─────────────────────────────────────────────────────────────────────────────
# HAVERSINE FALLBACK
# ─────────────────────────────────────────────────────────────────────────────


def _haversine_leg(origin, dest, speed_kmh: float = 30.0) -> tuple[list[dict], list[list[float]]]:
    """Single 'proceed to waypoint' step using great-circle distance."""
    dist_km = haversine_km(origin[0], origin[1], dest[0], dest[1]) * 1.35
    dur_s = (dist_km / speed_kmh) * 3600.0
    step = {
        "instruction": "Proceed to waypoint",
        "distance_m": round(dist_km * 1000.0, 1),
        "duration_s": round(dur_s, 1),
        "lon": dest[1],
        "lat": dest[0],
        "maneuver": "depart",
    }
    geometry = [[origin[1], origin[0]], [dest[1], dest[0]]]
    return [step], geometry


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINTS
# ─────────────────────────────────────────────────────────────────────────────


async def get_directions_for_leg(
    origin: tuple[float, float],
    dest: tuple[float, float],
    backend: str | None = None,
    speed_kmh: float = 30.0,
) -> dict:
    """
    Return directions for a single origin→dest leg.

    Result: {"steps": [DirectionStep, ...], "geometry": [[lon, lat], ...], "source": str}
    """
    effective = backend or settings.ROUTING_BACKEND

    cached = cache.get_directions(effective, origin, dest)
    if cached is not None:
        cached["steps"] = [DirectionStep(**s) for s in cached["steps"]]
        return cached

    try:
        if effective == "ors" and settings.ORS_API_KEY:
            async with httpx.AsyncClient() as client:
                raw_steps, geometry = await _ors_leg(client, origin, dest, settings.ORS_API_KEY)
            source = "ors"
        elif effective == "osrm":
            async with httpx.AsyncClient() as client:
                raw_steps, geometry = await _osrm_leg(client, origin, dest, settings.OSRM_BASE_URL)
            source = "osrm"
        else:
            raw_steps, geometry = _haversine_leg(origin, dest, speed_kmh)
            source = "haversine"
    except Exception as exc:
        logger.warning("directions_fallback_haversine", error=str(exc), backend=effective)
        raw_steps, geometry = _haversine_leg(origin, dest, speed_kmh)
        source = "haversine"

    steps = [DirectionStep(**s) for s in raw_steps]
    result = {"steps": steps, "geometry": geometry, "source": source}
    cache.set_directions(effective, origin, dest, result)
    return result


async def get_directions_for_route(
    coordinates: list[tuple[float, float]],
    backend: str | None = None,
    speed_kmh: float = 30.0,
) -> dict:
    """
    Return concatenated directions across a full ordered route.

    `coordinates` is the ordered [(lat, lon), ...] list of stops. Legs run in
    parallel; the flattened step list and polyline preserve route order.
    """
    if len(coordinates) < 2:
        return {"steps": [], "geometry": [], "source": "haversine"}

    legs = await asyncio.gather(
        *[
            get_directions_for_leg(
                coordinates[i],
                coordinates[i + 1],
                backend=backend,
                speed_kmh=speed_kmh,
            )
            for i in range(len(coordinates) - 1)
        ]
    )

    steps: list[DirectionStep] = []
    geometry: list[list[float]] = []
    source = "haversine"
    for leg in legs:
        source = leg["source"]
        for step in leg["steps"]:
            if steps and step.lat == steps[-1].lat and step.lon == steps[-1].lon:
                steps.pop()
            steps.append(step)
        for coord in leg["geometry"]:
            if geometry and geometry[-1] == coord:
                continue
            geometry.append(coord)

    return {"steps": steps, "geometry": geometry, "source": source}
