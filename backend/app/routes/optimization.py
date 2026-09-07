from __future__ import annotations

import asyncio
import functools
import uuid as _uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, is_db_enabled
from app.dependencies import ApiKeyPrincipal, get_current_principal, require_permission
from app.models.db import Company, OptimizationJob, User
from app.models.schemas import DirectionsResponse, OptimizeRequest, OptimizeResponse, ReplanRequest
from app.services import cache
from app.services.api_keys import PERMISSION_OPTIMIZE
from app.services.optimizer import run_optimization_sync
from app.services.plans import check_optimization_limit
from app.services.replan import PreviousJobNotFoundError, run_replan

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1", tags=["optimization"])

_DEFAULT_COMPANY_ID = _uuid.UUID("00000000-0000-0000-0000-000000000001")


# ─────────────────────────────────────────────────────────
# POST /optimize-routes
# ─────────────────────────────────────────────────────────
@router.post(
    "/optimize-routes",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Run VRP optimization",
    description=(
        "Submit a set of delivery locations and vehicle parameters. "
        "Returns optimized per-vehicle routes and any unserved locations."
    ),
)
async def optimize_routes(
    req: OptimizeRequest,
    run_id: str | None = Query(default=None, description="Client-generated run ID for progress polling"),
    db: AsyncSession = Depends(get_db),
    principal: User | ApiKeyPrincipal = Depends(require_permission(PERMISSION_OPTIMIZE)),
) -> OptimizeResponse:
    if req.traffic:
        if not settings.ORS_API_KEY:
            raise HTTPException(
                status_code=422,
                detail="traffic=true requires ORS_API_KEY to be configured on the server",
            )
        effective_backend = req.routing_backend or settings.ROUTING_BACKEND
        if effective_backend != "ors":
            raise HTTPException(
                status_code=422,
                detail=f"traffic=true requires the 'ors' routing backend (got {effective_backend!r})",
            )

    if db is not None and is_db_enabled():
        company_result = await db.execute(select(Company).where(Company.id == principal.company_id))
        company = company_result.scalar_one_or_none()
        if company:
            result_count = await db.execute(
                select(sa_func.count())
                .select_from(OptimizationJob)
                .where(
                    OptimizationJob.company_id == company.id,
                    OptimizationJob.created_at >= sa_func.date_trunc("month", sa_func.now()),
                )
            )
            month_count = result_count.scalar() or 0
            backend = req.routing_backend or "haversine"
            n_locs = len(req.deliveries) + len(req.depots)
            error = check_optimization_limit(company.plan, month_count, n_locs, backend)
            if error:
                raise HTTPException(status_code=403, detail=error)

    run_id = run_id or str(_uuid.uuid4())
    cache.set_progress(run_id, "queued", 0, "Request queued...")
    company_id = principal.company_id
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, functools.partial(run_optimization_sync, req, run_id, company_id))
        # Persist to PostgreSQL if available
        if db is not None and is_db_enabled():
            from app.services.job_store import persist_job

            await persist_job(db, company_id=company_id, req=req, resp=result)
        # Always cache in Redis/LRU
        cache.set_job(company_id, result.job_id, result.model_dump())
        return result
    except ValueError as exc:
        logger.warning("validation_error", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("optimize_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Optimization failed. Check server logs for details.",
        ) from exc


# ─────────────────────────────────────────────────────────
# POST /optimize-routes/replan
# ─────────────────────────────────────────────────────────
@router.post(
    "/optimize-routes/replan",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Ride-along re-optimization of a previous job",
    description=(
        "Re-solves only the remaining (non-delivered) stops of a previous job, "
        "seeding each route from a driver's live position. Persisted as a new "
        "job linked to the previous one."
    ),
)
async def replan_routes(
    req: ReplanRequest,
    db: AsyncSession = Depends(get_db),
    principal: User | ApiKeyPrincipal = Depends(require_permission(PERMISSION_OPTIMIZE)),
) -> OptimizeResponse:
    company_id = principal.company_id
    try:
        return await run_replan(db, company_id, req)
    except PreviousJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("replan_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Re-planning failed. Check server logs for details.",
        ) from exc


# ─────────────────────────────────────────────────────────
# GET /optimize-routes/{run_id}/status
# ─────────────────────────────────────────────────────────
@router.get(
    "/optimize-routes/{run_id}/status",
    summary="Poll solver progress for a running optimization",
)
async def get_optimization_status(run_id: str) -> dict:
    progress = cache.get_progress(run_id)
    if progress is None:
        return {"status": "unknown", "pct": 0, "message": "No progress data found"}
    return {"status": "running", **progress}


# ─────────────────────────────────────────────────────────
# GET /routes/{job_id}
# ─────────────────────────────────────────────────────────
@router.get(
    "/routes/{job_id}",
    response_model=OptimizeResponse,
    summary="Retrieve a previous optimization result",
)
async def get_routes(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    principal: User | ApiKeyPrincipal | None = Depends(get_current_principal),
) -> OptimizeResponse:
    company_id = principal.company_id if principal else _DEFAULT_COMPANY_ID
    result = None
    # Try PostgreSQL first
    if db is not None and is_db_enabled():
        from app.services.job_store import get_job_from_db

        result = await get_job_from_db(db, job_id, company_id)
    # Fallback to cache
    if result is None:
        result = cache.get_job(company_id, job_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No result found for job_id={job_id}.",
        )
    return OptimizeResponse(**result)


# ─────────────────────────────────────────────────────────
# GET /routes/{job_id}/export
# ─────────────────────────────────────────────────────────
@router.get(
    "/routes/{job_id}/export",
    summary="Export route as CSV, GPX, or KML",
)
async def export_routes(
    job_id: str,
    format: str = Query(default="csv", pattern="^(csv|gpx|kml)$"),
    db: AsyncSession = Depends(get_db),
    principal: User | ApiKeyPrincipal | None = Depends(get_current_principal),
) -> Response:
    company_id = principal.company_id if principal else _DEFAULT_COMPANY_ID
    result = None
    if db is not None and is_db_enabled():
        from app.services.job_store import get_job_from_db

        result = await get_job_from_db(db, job_id, company_id)
    if result is None:
        result = cache.get_job(company_id, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No result found for job_id={job_id}.")

    response = OptimizeResponse(**result)
    from app.services.export import (
        collect_route_directions,
        generate_csv,
        generate_gpx,
        generate_kml,
    )

    if format == "csv":
        legs_by_route = await collect_route_directions(response, backend=response.matrix_source)
        steps_by_stop = {}
        for vi, legs in legs_by_route.items():
            for leg_no, leg in enumerate(legs, start=2):  # stop_sequence 2 is the first stop
                if leg.get("steps"):
                    steps_by_stop[(vi, leg_no)] = leg["steps"][-1]
        content = generate_csv(response, steps_by_stop)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="route_{job_id[:8]}.csv"'},
        )
    if format == "gpx":
        content = generate_gpx(response)
        return Response(
            content=content,
            media_type="application/gpx+xml",
            headers={"Content-Disposition": f'attachment; filename="route_{job_id[:8]}.gpx"'},
        )
    legs_by_route = await collect_route_directions(response, backend=response.matrix_source)
    content = generate_kml(response, legs_by_route)
    return Response(
        content=content,
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="route_{job_id[:8]}.kml"'},
    )


# ─────────────────────────────────────────────────────────
# GET /routes/{job_id}/directions/route/{route_index}
# ─────────────────────────────────────────────────────────
@router.get(
    "/routes/{job_id}/directions/route/{route_index}",
    response_model=DirectionsResponse,
    summary="Turn-by-turn directions for one vehicle route",
    description=(
        "Returns step-by-step driving instructions covering the full ordered "
        "route (depot → stops → depot). Uses the same routing backend that "
        "built the distance matrix, with a haversine fallback."
    ),
)
async def get_route_directions(
    job_id: str,
    route_index: int,
    db: AsyncSession = Depends(get_db),
    principal: User | ApiKeyPrincipal | None = Depends(get_current_principal),
) -> DirectionsResponse:
    company_id = principal.company_id if principal else _DEFAULT_COMPANY_ID
    result = None
    if db is not None and is_db_enabled():
        from app.services.job_store import get_job_from_db

        result = await get_job_from_db(db, job_id, company_id)
    if result is None:
        result = cache.get_job(company_id, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No result found for job_id={job_id}.")

    response = OptimizeResponse(**result)
    if route_index < 0 or route_index >= len(response.vehicles):
        raise HTTPException(
            status_code=404,
            detail=f"No route at index {route_index} (job has {len(response.vehicles)} routes).",
        )

    route = response.vehicles[route_index]
    waypoints_by_id = {
        wp["id"]: wp for wp in route.waypoints if wp.get("id") is not None and "lat" in wp and "lon" in wp
    }
    coordinates = [
        (waypoints_by_id[lid]["lat"], waypoints_by_id[lid]["lon"]) for lid in route.route if lid in waypoints_by_id
    ]
    if len(coordinates) < 2:
        raise HTTPException(
            status_code=404,
            detail=f"Route at index {route_index} has fewer than two waypoints with coordinates.",
        )

    from app.services.directions import get_directions_for_route

    directions_result = await get_directions_for_route(coordinates, backend=response.matrix_source)
    return DirectionsResponse(
        job_id=job_id,
        route_index=route_index,
        source=directions_result["source"],
        steps=directions_result["steps"],
        geometry=directions_result["geometry"],
    )


# ─────────────────────────────────────────────────────────
# GET /routes  (list last N jobs – from in-process LRU)
# ─────────────────────────────────────────────────────────
@router.get(
    "/routes",
    summary="List recently computed optimization jobs",
)
async def list_routes(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    principal: User | ApiKeyPrincipal | None = Depends(get_current_principal),
) -> dict:
    company_id = principal.company_id if principal else _DEFAULT_COMPANY_ID
    # Try PostgreSQL first
    if db is not None and is_db_enabled():
        from app.services.job_store import list_jobs_from_db

        summaries = await list_jobs_from_db(db, company_id, limit=limit)
    else:
        summaries = cache.list_jobs(company_id, limit=limit)
    return {"count": len(summaries), "jobs": summaries}
