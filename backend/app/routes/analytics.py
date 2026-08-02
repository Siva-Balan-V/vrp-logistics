"""
Business Intelligence & Analytics endpoints.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.db import Location as LocationModel
from app.models.db import OptimizationJob, User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/bi", tags=["bi"])


@router.get("/dashboard")
async def dashboard(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Aggregated BI metrics for dashboard."""
    company_id = user.company_id

    # all jobs in date range
    result = await db.execute(
        select(OptimizationJob)
        .where(
            OptimizationJob.company_id == company_id,
            OptimizationJob.created_at >= func.now() - func.make_interval(days=days),
        )
        .order_by(desc(OptimizationJob.created_at))
    )
    jobs = result.scalars().all()

    total_jobs = len(jobs)
    if total_jobs == 0:
        return {
            "total_jobs": 0,
            "success_rate": 0,
            "avg_distance_km": 0,
            "avg_solver_time_s": 0,
            "avg_vehicles_used": 0,
            "total_locations_served": 0,
            "daily_trend": [],
            "recent_jobs": [],
        }

    success_count = sum(1 for j in jobs if j.status == "success")
    total_assigned = sum(j.assigned_count or 0 for j in jobs)
    distances = [j.total_distance_km for j in jobs if j.total_distance_km is not None]
    solver_times = [j.solver_time_s for j in jobs if j.solver_time_s is not None]
    vehicles = [j.n_vehicles for j in jobs if j.n_vehicles is not None]

    # daily trend
    from collections import defaultdict

    daily: dict[str, dict] = defaultdict(lambda: {"jobs": 0, "distance": 0.0, "locs": 0})
    for j in jobs:
        day = j.created_at.date().isoformat() if j.created_at else "unknown"
        daily[day]["jobs"] += 1
        daily[day]["distance"] += j.total_distance_km or 0
        daily[day]["locs"] += j.assigned_count or 0

    daily_trend = [
        {"date": d, "jobs": v["jobs"], "distance_km": round(v["distance"], 1), "locations": v["locs"]}
        for d, v in sorted(daily.items())
    ]

    recent = [
        {
            "job_id": str(j.job_id),
            "status": j.status,
            "total_locations": j.n_locations,
            "assigned_count": j.assigned_count,
            "total_distance_km": j.total_distance_km,
            "solver_time_seconds": j.solver_time_s,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs[:10]
    ]

    return {
        "total_jobs": total_jobs,
        "success_rate": round(success_count / total_jobs * 100, 1) if total_jobs > 0 else 0,
        "avg_distance_km": round(sum(distances) / len(distances), 1) if distances else 0,
        "avg_solver_time_s": round(sum(solver_times) / len(solver_times), 1) if solver_times else 0,
        "avg_vehicles_used": round(sum(vehicles) / len(vehicles), 1) if vehicles else 0,
        "total_locations_served": total_assigned,
        "daily_trend": daily_trend,
        "recent_jobs": recent,
    }


@router.get("/territory")
async def territory(
    job_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Delivery density clusters for territory analysis."""
    company_id = user.company_id

    if job_id:
        result = await db.execute(
            select(LocationModel)
            .join(OptimizationJob, LocationModel.job_id == OptimizationJob.job_id)
            .where(
                OptimizationJob.company_id == company_id,
                OptimizationJob.job_id == uuid.UUID(job_id),
                ~LocationModel.is_depot,
            )
        )
    else:
        result = await db.execute(
            select(LocationModel)
            .join(OptimizationJob, LocationModel.job_id == OptimizationJob.job_id)
            .where(
                OptimizationJob.company_id == company_id,
                ~LocationModel.is_depot,
            )
            .order_by(desc(OptimizationJob.created_at))
            .limit(500)
        )
    locs = result.scalars().all()

    from collections import defaultdict

    grid: dict[str, dict] = defaultdict(lambda: {"count": 0, "assigned": 0, "lats": [], "lons": []})
    for loc in locs:
        key = f"{round(loc.lat, 2)},{round(loc.lon, 2)}"
        grid[key]["count"] += 1
        grid[key]["lats"].append(loc.lat)
        grid[key]["lons"].append(loc.lon)
        if loc.assigned:
            grid[key]["assigned"] += 1

    clusters = [
        {
            "lat": sum(v["lats"]) / len(v["lats"]),
            "lon": sum(v["lons"]) / len(v["lons"]),
            "count": v["count"],
            "assigned": v["assigned"],
        }
        for v in grid.values()
    ]
    clusters.sort(key=lambda c: c["count"], reverse=True)

    return {"total_locations": len(locs), "clusters": clusters[:200]}
