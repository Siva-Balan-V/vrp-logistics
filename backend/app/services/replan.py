"""
Ride-along re-optimization (Phase 8.6).

Takes a previous optimization job plus the fleet's live driver positions and
re-solves only the remaining (non-delivered) stops. Each driver's current
position is seeded into the solver as a depot node so every route starts from
where its driver actually is, keeping the existing depot/vehicle constraints.
"""

from __future__ import annotations

import asyncio
import functools
import uuid

import structlog
from sqlalchemy import select

from app.database import is_db_enabled
from app.models.db import OptimizationJob
from app.models.schemas import (
    Location,
    OptimizeRequest,
    OptimizeResponse,
    ReplanDriver,
    ReplanRequest,
    VehicleSpec,
)
from app.services import cache
from app.services.job_store import persist_job
from app.services.optimizer import run_optimization_sync

logger = structlog.get_logger(__name__)


class PreviousJobNotFoundError(Exception):
    """Raised when the previous optimization job cannot be resolved."""


async def _load_previous_job(db, company_id: uuid.UUID, previous_job_id: str) -> tuple[OptimizeResponse, dict | None]:
    """Resolve the previous job result from PostgreSQL, falling back to cache."""
    resp_dict = None
    req_dict = None
    if db is not None and is_db_enabled():
        try:
            job_uuid = uuid.UUID(previous_job_id)
        except (ValueError, AttributeError, TypeError):
            job_uuid = None
        if job_uuid is not None:
            result = await db.execute(
                select(OptimizationJob).where(
                    OptimizationJob.job_id == job_uuid,
                    OptimizationJob.company_id == company_id,
                )
            )
            job = result.scalar_one_or_none()
            if job is not None:
                resp_dict = job.response_json
                req_dict = job.request_json

    if resp_dict is None:
        resp_dict = cache.get_job(company_id, previous_job_id)
    if resp_dict is None:
        logger.warning("replan_previous_missing", previous_job_id=previous_job_id)
        raise PreviousJobNotFoundError(f"No result found for job_id={previous_job_id}.")

    return OptimizeResponse(**resp_dict), req_dict


def _collect_remaining_stops(previous: OptimizeResponse, req_dict: dict | None) -> list[Location]:
    """Gather stops that still need delivering (status != delivered) across all routes."""
    depot_ids = set()
    waypoints_by_id: dict[int, dict] = {}
    for vr in previous.vehicles:
        if vr.route:
            depot_ids.add(vr.route[0])
        for wp in vr.waypoints:
            if wp.get("id") is None or "lat" not in wp or "lon" not in wp:
                continue
            waypoints_by_id[wp["id"]] = wp

    request_deliveries: dict[int, Location] = {}
    if req_dict:
        try:
            prev_req = OptimizeRequest(**req_dict)
            request_deliveries = {loc.id: loc for loc in prev_req.deliveries}
        except Exception:
            logger.warning("replan_request_json_unparseable")
            request_deliveries = {}

    remaining_ids: list[int] = []
    for wp_id, wp in waypoints_by_id.items():
        if wp_id not in depot_ids and wp.get("status", "pending") != "delivered":
            remaining_ids.append(wp_id)
    # Previously unassigned stops are still pending delivery — pull them back in
    # when the original request is available (gives us their coordinates).
    for unassigned_id in previous.unassigned or []:
        if unassigned_id in request_deliveries and unassigned_id not in depot_ids:
            remaining_ids.append(unassigned_id)

    locations: list[Location] = []
    for lid in remaining_ids:
        if lid in request_deliveries:
            locations.append(request_deliveries[lid])
        else:
            wp = waypoints_by_id[lid]
            locations.append(
                Location(
                    id=lid,
                    lat=wp["lat"],
                    lon=wp["lon"],
                    demand=1,
                    label=wp.get("label"),
                    priority=wp.get("priority", 1),
                )
            )
    return locations


def _build_depot_locations(
    previous: OptimizeResponse,
    req_dict: dict | None,
    drivers: list[ReplanDriver],
) -> list[Location]:
    """Seed a synthetic depot per live driver; fall back to the previous depots."""
    if drivers:
        return [
            Location(
                id=-(i + 1),
                lat=driver.lat,
                lon=driver.lon,
                demand=0,
                label=f"Driver {str(driver.driver_id)[:8]} start",
                priority=1,
            )
            for i, driver in enumerate(drivers)
        ]

    if req_dict:
        try:
            prev_req = OptimizeRequest(**req_dict)
            if prev_req.depots:
                return list(prev_req.depots)
        except Exception:
            pass

    depots: list[Location] = []
    seen: set[int] = set()
    for vr in previous.vehicles:
        if not vr.route or vr.route[0] in seen:
            continue
        depot_id = vr.route[0]
        waypoint = next(
            (wp for wp in vr.waypoints if wp.get("id") == depot_id and "lat" in wp and "lon" in wp),
            None,
        )
        if waypoint is not None:
            depots.append(Location(id=depot_id, lat=waypoint["lat"], lon=waypoint["lon"], demand=0, label="Depot"))
            seen.add(depot_id)
    return depots


def _resolve_vehicle_spec(req: ReplanRequest, req_dict: dict | None) -> VehicleSpec:
    """Use an explicit override, else the previous request's spec, else defaults."""
    spec = req.vehicles
    if spec is None and req_dict:
        try:
            spec = OptimizeRequest(**req_dict).vehicles
        except Exception:
            spec = None
    if spec is None:
        spec = VehicleSpec()
    # Guarantee a start per live driver (extra vehicles are simply unused).
    if req.drivers and spec.count < len(req.drivers):
        spec = spec.model_copy(update={"count": len(req.drivers)})
    return spec


async def run_replan(db, company_id: uuid.UUID, req: ReplanRequest) -> OptimizeResponse:
    """Re-solve the remaining fleet stops from live driver positions."""
    previous, req_dict = await _load_previous_job(db, company_id, req.previous_job_id)

    remaining = _collect_remaining_stops(previous, req_dict)
    if not remaining:
        logger.info(
            "replan_no_remaining_stops",
            previous_job_id=req.previous_job_id,
            delivered=previous.total_locations - previous.unassigned_count,
        )
        raise ValueError("All stops are already delivered; nothing to re-plan.")

    depots = _build_depot_locations(previous, req_dict, req.drivers)
    if not depots:
        raise ValueError("Could not determine depot/start locations for re-planning.")

    vehicles = _resolve_vehicle_spec(req, req_dict)

    new_job_id = str(uuid.uuid4())
    sub_req = OptimizeRequest(
        job_id=new_job_id,
        depots=depots,
        deliveries=remaining,
        vehicles=vehicles,
        routing_backend=req.routing_backend,
        traffic=req.traffic,
    )

    logger.info(
        "replan_start",
        previous_job_id=req.previous_job_id,
        job_id=new_job_id,
        remaining=len(remaining),
        drivers=len(req.drivers),
    )
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        functools.partial(run_optimization_sync, sub_req, new_job_id, company_id),
    )
    result = result.model_copy(update={"previous_job_id": req.previous_job_id})

    if db is not None and is_db_enabled():
        try:
            await persist_job(
                db,
                company_id=company_id,
                req=sub_req,
                resp=result,
                previous_job_id=req.previous_job_id,
            )
        except Exception:
            logger.exception("replan_persist_failed", job_id=new_job_id)
    cache.set_job(company_id, result.job_id, result.model_dump())

    logger.info(
        "replan_complete",
        previous_job_id=req.previous_job_id,
        job_id=result.job_id,
        vehicles_used=result.vehicles_used,
    )
    return result
