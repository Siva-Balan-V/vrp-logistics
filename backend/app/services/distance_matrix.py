"""
Distance / Travel-Time Matrix Service
Supports three backends (in order of accuracy):
  1. OSRM   – free, self-hosted or public router.project-osrm.org
  2. ORS    – OpenRouteService (needs API key)
  3. Haversine – pure-Python great-circle fallback (no API needed)
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import Optional

import httpx
import numpy as np
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# HAVERSINE HELPER
# ─────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ─────────────────────────────────────────────────────────────────────────────
# HAVERSINE MATRIX (no API calls)
# ─────────────────────────────────────────────────────────────────────────────

def build_haversine_matrix(
    coords: list[tuple[float, float]],
    speed_kmh: float = 30.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (distance_matrix_km, duration_matrix_seconds).
    Applies a road-network correction factor of 1.35 over straight-line distance.
    """
    n = len(coords)
    dist = np.zeros((n, n), dtype=np.float64)
    lats = np.array([c[0] for c in coords])
    lons = np.array([c[1] for c in coords])

    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(lats[i], lons[i], lats[j], lons[j])
            d_road = d * 1.35          # empirical road-network factor
            dist[i, j] = d_road
            dist[j, i] = d_road

    duration = (dist / speed_kmh) * 3600.0  # seconds
    return dist, duration


# ─────────────────────────────────────────────────────────────────────────────
# OSRM TABLE (batch, free public endpoint)
# ─────────────────────────────────────────────────────────────────────────────

async def _osrm_table_chunk(
    client: httpx.AsyncClient,
    coords: list[tuple[float, float]],
    sources: list[int],
    destinations: list[int],
    base_url: str,
) -> tuple[list[list[float]], list[list[float]]]:
    """Call OSRM /table endpoint for a chunk of source × destination pairs."""
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    src_str = ";".join(map(str, sources))
    dst_str = ";".join(map(str, destinations))
    url = (
        f"{base_url}/table/v1/driving/{coord_str}"
        f"?sources={src_str}&destinations={dst_str}"
        f"&annotations=duration,distance"
    )
    resp = await client.get(url, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    durations = data.get("durations", [])
    distances = data.get("distances", [])
    return durations, distances


async def build_osrm_matrix(
    coords: list[tuple[float, float]],
    speed_kmh: float = 30.0,
    base_url: str | None = None,
    batch_size: int = 100,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build full n×n matrices using OSRM table API.
    Chunks the request when n > batch_size.
    Falls back to haversine on error.
    """
    base_url = base_url or settings.OSRM_BASE_URL
    n = len(coords)

    duration_m = np.zeros((n, n), dtype=np.float64)
    distance_m = np.zeros((n, n), dtype=np.float64)

    try:
        async with httpx.AsyncClient() as client:
            if n <= batch_size:
                all_idx = list(range(n))
                durations, distances = await _osrm_table_chunk(
                    client, coords, all_idx, all_idx, base_url
                )
                for i in range(n):
                    for j in range(n):
                        duration_m[i][j] = durations[i][j] if durations[i][j] else 0.0
                        distance_m[i][j] = (distances[i][j] / 1000.0) if (distances and distances[i][j]) else 0.0
            else:
                # Chunked requests: iterate over source batches
                tasks = []
                chunk_meta = []
                for s_start in range(0, n, batch_size):
                    s_end = min(s_start + batch_size, n)
                    sources = list(range(s_start, s_end))
                    destinations = list(range(n))
                    tasks.append(
                        _osrm_table_chunk(client, coords, sources, destinations, base_url)
                    )
                    chunk_meta.append((s_start, s_end))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for (s_start, s_end), result in zip(chunk_meta, results):
                    if isinstance(result, Exception):
                        logger.warning("osrm_chunk_failed", error=str(result))
                        # Fill with haversine for this chunk
                        for i in range(s_start, s_end):
                            for j in range(n):
                                d = haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1]) * 1.35
                                distance_m[i][j] = d
                                duration_m[i][j] = (d / speed_kmh) * 3600
                        continue
                    durations, distances = result
                    for ri, i in enumerate(range(s_start, s_end)):
                        for j in range(n):
                            duration_m[i][j] = durations[ri][j] if durations[ri][j] else 0.0
                            distance_m[i][j] = (distances[ri][j] / 1000.0) if (distances and distances[ri][j]) else 0.0

        logger.info("osrm_matrix_built", n=n, batch_size=batch_size)
        return distance_m, duration_m

    except Exception as exc:
        logger.warning("osrm_failed_fallback_haversine", error=str(exc))
        return build_haversine_matrix(coords, speed_kmh)


# ─────────────────────────────────────────────────────────────────────────────
# ORS MATRIX (OpenRouteService – needs API key)
# ─────────────────────────────────────────────────────────────────────────────

async def build_ors_matrix(
    coords: list[tuple[float, float]],
    api_key: str,
    speed_kmh: float = 30.0,
    batch_size: int = 50,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build matrices using ORS /v2/matrix/driving-car endpoint.
    ORS accepts max 50 locations per request on the free tier.
    """
    n = len(coords)
    duration_m = np.zeros((n, n), dtype=np.float64)
    distance_m = np.zeros((n, n), dtype=np.float64)

    ors_coords = [[lon, lat] for lat, lon in coords]   # ORS uses [lon, lat]
    url = "https://api.openrouteservice.org/v2/matrix/driving-car"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        for s_start in range(0, n, batch_size):
            s_end = min(s_start + batch_size, n)
            sources = list(range(s_start, s_end))
            payload = {
                "locations": ors_coords,
                "sources": sources,
                "destinations": list(range(n)),
                "metrics": ["duration", "distance"],
                "units": "km",
            }
            try:
                resp = await client.post(url, json=payload, headers=headers, timeout=60.0)
                resp.raise_for_status()
                data = resp.json()
                for ri, i in enumerate(range(s_start, s_end)):
                    for j in range(n):
                        duration_m[i][j] = data["durations"][ri][j] or 0.0
                        distance_m[i][j] = data["distances"][ri][j] or 0.0
            except Exception as exc:
                logger.warning("ors_chunk_failed", error=str(exc), s_start=s_start)
                # Haversine fallback for this chunk
                for i in range(s_start, s_end):
                    for j in range(n):
                        d = haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1]) * 1.35
                        distance_m[i][j] = d
                        duration_m[i][j] = (d / speed_kmh) * 3600

    logger.info("ors_matrix_built", n=n)
    return distance_m, duration_m


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def build_matrix(
    coords: list[tuple[float, float]],
    backend: Optional[str] = None,
    speed_kmh: float = 30.0,
) -> tuple[np.ndarray, np.ndarray, str]:
    """
    Returns (distance_km_matrix, duration_seconds_matrix, backend_used).

    Backend priority:
      1. Explicit `backend` param  →  "osrm" | "ors" | "haversine"
      2. settings.ROUTING_BACKEND
      3. Auto-detect based on available keys
    """
    t0 = time.perf_counter()
    effective = backend or settings.ROUTING_BACKEND

    if effective == "ors" and settings.ORS_API_KEY:
        dist, dur = await build_ors_matrix(coords, settings.ORS_API_KEY, speed_kmh)
        source = "ors"
    elif effective == "osrm":
        dist, dur = await build_osrm_matrix(coords, speed_kmh)
        source = "osrm"
    else:
        dist, dur = build_haversine_matrix(coords, speed_kmh)
        source = "haversine"

    elapsed = time.perf_counter() - t0
    logger.info("matrix_built", n=len(coords), source=source, elapsed_s=round(elapsed, 2))
    return dist, dur, source
