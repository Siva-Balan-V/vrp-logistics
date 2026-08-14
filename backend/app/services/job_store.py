"""
PostgreSQL-backed job persistence for optimization results.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Location, OptimizationJob, VehicleRoute
from app.models.schemas import OptimizeRequest, OptimizeResponse

logger = structlog.get_logger(__name__)


async def persist_job(
    db: AsyncSession,
    company_id: uuid.UUID,
    req: OptimizeRequest,
    resp: OptimizeResponse,
) -> None:
    """Save optimization job and results to PostgreSQL."""
    job = OptimizationJob(
        job_id=uuid.UUID(resp.job_id),
        company_id=company_id,
        status=resp.status,
        n_locations=resp.total_locations,
        n_vehicles=resp.vehicles_used,
        routing_backend=req.routing_backend or "haversine",
        solver_time_s=resp.solver_time_seconds,
        total_distance_km=resp.total_distance_km,
        total_time_min=resp.total_time_minutes,
        assigned_count=resp.assigned_count,
        unassigned_count=resp.unassigned_count,
        request_json=req.model_dump(mode="json"),
        response_json=resp.model_dump(mode="json"),
    )
    db.add(job)

    for vr in resp.vehicles:
        route = VehicleRoute(
            job_id=uuid.UUID(resp.job_id),
            vehicle_id=vr.vehicle_id,
            route_json=vr.model_dump(mode="json"),
            distance_km=vr.distance_km,
            time_minutes=vr.time_minutes,
            packages=vr.packages_delivered,
        )
        db.add(route)

    unassigned_set = set(resp.unassigned or [])
    for loc in req.deliveries:
        is_assigned = loc.id not in unassigned_set
        vehicle = None
        if is_assigned:
            for vr in resp.vehicles:
                if loc.id in vr.route:
                    vehicle = vr.vehicle_id
                    break
        db.add(
            Location(
                job_id=uuid.UUID(resp.job_id),
                location_id=loc.id,
                lat=loc.lat,
                lon=loc.lon,
                demand=loc.demand,
                label=loc.label,
                is_depot=False,
                assigned=is_assigned,
                vehicle_id=vehicle,
            )
        )

    # Add depot location(s)
    for depot in req.depots:
        db.add(
            Location(
                job_id=uuid.UUID(resp.job_id),
                location_id=depot.id,
                lat=depot.lat,
                lon=depot.lon,
                demand=depot.demand,
                label=depot.label,
                is_depot=True,
                assigned=True,
            )
        )

    await db.flush()
    logger.info("job_persisted", job_id=resp.job_id, company_id=str(company_id))


async def get_job_from_db(db: AsyncSession, job_id: str, company_id: uuid.UUID) -> dict | None:
    """Retrieve job result from PostgreSQL."""
    try:
        job_uuid = uuid.UUID(job_id)
    except (ValueError, AttributeError, TypeError):
        return None
    result = await db.execute(
        select(OptimizationJob).where(
            OptimizationJob.job_id == job_uuid,
            OptimizationJob.company_id == company_id,
        )
    )
    job = result.scalar_one_or_none()
    if job and job.response_json:
        return job.response_json
    return None


async def list_jobs_from_db(db: AsyncSession, company_id: uuid.UUID, limit: int = 10) -> list[dict]:
    """List recent jobs from PostgreSQL."""
    result = await db.execute(
        select(OptimizationJob)
        .where(OptimizationJob.company_id == company_id)
        .order_by(desc(OptimizationJob.created_at))
        .limit(limit)
    )
    return [
        {
            "job_id": str(j.job_id),
            "status": j.status,
            "total_locations": j.n_locations,
            "assigned_count": j.assigned_count,
            "unassigned_count": j.unassigned_count,
            "vehicles_used": j.n_vehicles,
            "total_distance_km": j.total_distance_km,
            "solver_time_seconds": j.solver_time_s,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in result.scalars().all()
    ]
