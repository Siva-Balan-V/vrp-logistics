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

from app.database import get_db, is_db_enabled
from app.dependencies import ApiKeyPrincipal, get_current_principal, require_permission
from app.models.db import Company, OptimizationJob, User
from app.models.schemas import OptimizeRequest, OptimizeResponse
from app.services import cache
from app.services.api_keys import PERMISSION_OPTIMIZE
from app.services.optimizer import run_optimization_sync
from app.services.plans import check_optimization_limit

logger = structlog.get_logger(__name__)

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
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, functools.partial(run_optimization_sync, req, run_id))
        company_id = principal.company_id
        # Persist to PostgreSQL if available
        if db is not None and is_db_enabled():
            from app.services.job_store import persist_job

            await persist_job(db, company_id=company_id, req=req, resp=result)
        # Always cache in Redis/LRU
        cache.set_job(result.job_id, result.model_dump())
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
        result = cache.get_job(job_id)
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
    summary="Export route as CSV or GPX",
)
async def export_routes(
    job_id: str,
    format: str = Query(default="csv", pattern="^(csv|gpx)$"),
    db: AsyncSession = Depends(get_db),
    principal: User | ApiKeyPrincipal | None = Depends(get_current_principal),
) -> Response:
    company_id = principal.company_id if principal else _DEFAULT_COMPANY_ID
    result = None
    if db is not None and is_db_enabled():
        from app.services.job_store import get_job_from_db

        result = await get_job_from_db(db, job_id, company_id)
    if result is None:
        result = cache.get_job(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No result found for job_id={job_id}.")

    response = OptimizeResponse(**result)
    from app.services.export import generate_csv, generate_gpx

    if format == "csv":
        content = generate_csv(response)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="route_{job_id[:8]}.csv"'},
        )
    else:
        content = generate_gpx(response)
        return Response(
            content=content,
            media_type="application/gpx+xml",
            headers={"Content-Disposition": f'attachment; filename="route_{job_id[:8]}.gpx"'},
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
        summaries = cache.list_jobs(limit=limit)
    return {"count": len(summaries), "jobs": summaries}
