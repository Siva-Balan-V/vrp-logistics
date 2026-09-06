"""
Orchestration service: builds matrix → runs solver → formats response.
"""

from __future__ import annotations

import time
import uuid

import structlog

from app.config import get_settings
from app.middleware.metrics import SOLVER_DURATION, SOLVER_RESULT
from app.models.schemas import (
    Location,
    OptimizeRequest,
    OptimizeResponse,
    VehicleRoute,
)
from app.optimization.vrp_solver import VRPInput, solve_vrp
from app.services import cache
from app.services import distance_matrix as dm_service

logger = structlog.get_logger(__name__)
settings = get_settings()


async def run_optimization(req: OptimizeRequest, run_id: str | None = None, company_id=None) -> OptimizeResponse:
    """Async entry point: builds distance matrix, then delegates sync solver."""
    job_id = req.job_id or str(uuid.uuid4())
    run_id = run_id or job_id
    logger.info("optimization_start", job_id=job_id, n=len(req.deliveries))

    cache.set_progress(run_id, "preparing", 0, "Preparing locations and parameters...")

    # ── Build ordered location list (depots first, then deliveries) ───────────
    all_locs: list[Location] = list(req.depots) + list(req.deliveries)
    num_depots = len(req.depots)
    coords: list[tuple[float, float]] = [(loc.lat, loc.lon) for loc in all_locs]
    location_ids: list[int] = [loc.id for loc in all_locs]
    demands: list[int] = [loc.demand for loc in all_locs]
    label_map: dict[int, str | None] = {loc.id: loc.label for loc in all_locs}

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

    # Extract priorities
    priorities = [loc.priority for loc in all_locs]

    backend = req.routing_backend or settings.ROUTING_BACKEND

    # ── Distance matrix (cached) ──────────────────────────────────────────────
    cache.set_progress(run_id, "matrix", 10, "Building distance matrix...")
    cached = cache.get_matrix(coords, backend)
    if cached:
        dist_km, dur_s, matrix_source = cached
        logger.info("matrix_from_cache", job_id=job_id)
    else:
        dist_km, dur_s, matrix_source = await dm_service.build_matrix(
            coords,
            backend=backend,
            speed_kmh=req.vehicles.speed_kmh,
            traffic=req.traffic,
        )
        cache.set_matrix(coords, backend, (dist_km, dur_s, matrix_source))

    # ── Solver input ──────────────────────────────────────────────────────────
    cache.set_progress(run_id, "solving", 30, "Solving VRP with OR-Tools...")
    vrp_input = VRPInput(
        num_vehicles=req.vehicles.count,
        vehicle_capacity=req.vehicles.capacity,
        max_route_duration_seconds=req.vehicles.max_route_duration_seconds,
        distance_matrix=dist_km,
        duration_matrix=dur_s,
        demands=demands,
        location_ids=location_ids,
        speed_kmh=req.vehicles.speed_kmh,
        solver_time_limit_seconds=req.vehicles.solver_time_limit_seconds or settings.SOLVER_TIME_LIMIT_SECONDS,
        solver_algorithm=req.vehicles.solver_algorithm or "gls",
        time_windows=time_windows,
        num_depots=num_depots,
        priorities=priorities,
    )

    # ── Solve (CPU-bound, runs in thread executor by caller) ──────────────────
    cache.set_progress(run_id, "solving", 50, "Optimizing routes (GUIDED_LOCAL_SEARCH)...")
    _t0 = time.perf_counter()
    output = solve_vrp(vrp_input)
    SOLVER_DURATION.observe(time.perf_counter() - _t0)
    SOLVER_RESULT.labels(
        status="success" if len(output.routes) > 0 else "no_routes",
    ).inc()

    # ── Format routes ─────────────────────────────────────────────────────────
    cache.set_progress(run_id, "formatting", 90, "Formatting results...")
    result = _format_response(req, job_id, output, all_locs, location_ids, demands, label_map, matrix_source)

    cache.set_job(company_id, job_id, result.model_dump())
    cache.set_progress(run_id, "done", 100, "Complete!")
    cache.clear_progress(run_id)
    return result


def run_optimization_sync(req: OptimizeRequest, run_id: str | None = None, company_id=None) -> OptimizeResponse:
    """Synchronous entry point for thread executor."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_optimization(req, run_id=run_id, company_id=company_id))
    finally:
        loop.close()


def _format_response(
    req: OptimizeRequest,
    job_id: str,
    output,
    all_locs: list[Location],
    location_ids: list[int],
    demands: list[int],
    label_map: dict[int, str | None],
    matrix_source: str,
) -> OptimizeResponse:
    loc_by_id = {loc.id: loc for loc in all_locs}

    vehicle_routes: list[VehicleRoute] = []
    total_dist = 0.0
    total_time = 0.0

    for rr in output.routes:
        waypoints = [
            {
                "id": lid,
                "lat": loc_by_id[lid].lat,
                "lon": loc_by_id[lid].lon,
                "priority": loc_by_id[lid].priority,
                "status": "pending",
            }
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

    # Cost estimation
    fuel_cost = total_dist * settings.FUEL_COST_PER_KM
    driver_cost = (total_time / 60) * settings.DRIVER_COST_PER_HOUR

    depot_ids = {d.id for d in req.depots}
    assigned_ids = {lid for rr in output.routes for lid in rr.location_ids if lid not in depot_ids}

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
        fuel_cost=round(fuel_cost, 2),
        driver_cost=round(driver_cost, 2),
        total_cost=round(fuel_cost + driver_cost, 2),
    )

    logger.info(
        "optimization_complete",
        job_id=job_id,
        vehicles_used=len(vehicle_routes),
        unassigned=len(output.unassigned_ids),
        total_dist_km=round(total_dist, 2),
    )
    return response
