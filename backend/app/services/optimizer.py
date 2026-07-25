"""
Orchestration service: builds matrix → runs solver → formats response.
"""

from __future__ import annotations

import uuid
from typing import Optional

import numpy as np
import structlog

from app.config import get_settings
from app.models.schemas import (
    Location,
    OptimizeRequest,
    OptimizeResponse,
    VehicleRoute,
)
from app.optimization.vrp_solver import VRPInput, solve_vrp
from app.services import cache, distance_matrix as dm_service

logger = structlog.get_logger(__name__)
settings = get_settings()


async def run_optimization(req: OptimizeRequest) -> OptimizeResponse:
    """Async entry point: builds distance matrix, then delegates sync solver."""
    job_id = req.job_id or str(uuid.uuid4())
    logger.info("optimization_start", job_id=job_id, n=len(req.deliveries))

    # ── Build ordered location list (depot first) ─────────────────────────────
    all_locs: list[Location] = [req.depot] + req.deliveries
    coords: list[tuple[float, float]] = [(loc.lat, loc.lon) for loc in all_locs]
    location_ids: list[int] = [loc.id for loc in all_locs]
    demands: list[int] = [loc.demand for loc in all_locs]
    label_map: dict[int, Optional[str]] = {loc.id: loc.label for loc in all_locs}

    # Extract time windows (if any location has them)
    has_tw = any(loc.time_window_start is not None for loc in all_locs)
    time_windows = None
    if has_tw:
        time_windows = []
        for loc in all_locs:
            if loc.time_window_start is not None and loc.time_window_end is not None:
                time_windows.append((loc.time_window_start, loc.time_window_end))
            else:
                time_windows.append((0, req.vehicles.max_route_duration_seconds))

    backend = req.routing_backend or settings.ROUTING_BACKEND

    # ── Distance matrix (cached) ──────────────────────────────────────────────
    cached = cache.get_matrix(coords, backend)
    if cached:
        dist_km, dur_s, matrix_source = cached
        logger.info("matrix_from_cache", job_id=job_id)
    else:
        dist_km, dur_s, matrix_source = await dm_service.build_matrix(
            coords, backend=backend, speed_kmh=req.vehicles.speed_kmh
        )
        cache.set_matrix(coords, backend, (dist_km, dur_s, matrix_source))

    # ── Solver input ──────────────────────────────────────────────────────────
    vrp_input = VRPInput(
        num_vehicles=req.vehicles.count,
        vehicle_capacity=req.vehicles.capacity,
        max_route_duration_seconds=req.vehicles.max_route_duration_seconds,
        distance_matrix=dist_km,
        duration_matrix=dur_s,
        demands=demands,
        location_ids=location_ids,
        speed_kmh=req.vehicles.speed_kmh,
        solver_time_limit_seconds=settings.SOLVER_TIME_LIMIT_SECONDS,
        time_windows=time_windows,
    )

    # ── Solve (CPU-bound, runs in thread executor by caller) ──────────────────
    output = solve_vrp(vrp_input)

    # ── Format routes ─────────────────────────────────────────────────────────
    return _format_response(req, job_id, output, all_locs, location_ids, demands, label_map, matrix_source)


def run_optimization_sync(req: OptimizeRequest) -> OptimizeResponse:
    """Synchronous entry point for thread executor — skips matrix building."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_optimization(req))
    finally:
        loop.close()


def _format_response(
    req: OptimizeRequest,
    job_id: str,
    output,
    all_locs: list[Location],
    location_ids: list[int],
    demands: list[int],
    label_map: dict[int, Optional[str]],
    matrix_source: str,
) -> OptimizeResponse:
    loc_by_id = {loc.id: loc for loc in all_locs}

    vehicle_routes: list[VehicleRoute] = []
    total_dist = 0.0
    total_time = 0.0

    for rr in output.routes:
        waypoints = [
            {"id": lid, "lat": loc_by_id[lid].lat, "lon": loc_by_id[lid].lon}
            for lid in rr.location_ids
            if lid in loc_by_id
        ]
        vr = VehicleRoute(
            vehicle_id=rr.vehicle_id,
            route=rr.location_ids,
            route_labels=[label_map.get(lid) for lid in rr.location_ids],
            distance_km=rr.distance_km,
            time_minutes=round(rr.time_seconds / 60, 1),
            packages_delivered=rr.packages_delivered,
            waypoints=waypoints,
            arrival_times=rr.arrival_times,
        )
        vehicle_routes.append(vr)
        total_dist += rr.distance_km
        total_time += rr.time_seconds / 60

    assigned_ids = {lid for rr in output.routes for lid in rr.location_ids if lid != req.depot.id}

    response = OptimizeResponse(
        job_id=job_id,
        status="success",
        solver_time_seconds=output.solver_time_seconds,
        total_locations=len(req.deliveries),
        assigned_count=len(assigned_ids),
        unassigned_count=len(output.unassigned_ids),
        vehicles_used=len(vehicle_routes),
        total_distance_km=round(total_dist, 3),
        total_time_minutes=round(total_time, 1),
        vehicles=vehicle_routes,
        unassigned=output.unassigned_ids,
        unassigned_labels=[label_map.get(i) for i in output.unassigned_ids],
        matrix_source=matrix_source,
    )

    cache.set_job(job_id, response.model_dump())
    logger.info(
        "optimization_complete",
        job_id=job_id,
        vehicles_used=len(vehicle_routes),
        unassigned=len(output.unassigned_ids),
        total_dist_km=round(total_dist, 2),
    )
    return response
