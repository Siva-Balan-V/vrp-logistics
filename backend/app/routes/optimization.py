from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.models.schemas import ErrorResponse, OptimizeRequest, OptimizeResponse
from app.services import cache
from app.services.optimizer import run_optimization

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["optimization"])


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
async def optimize_routes(req: OptimizeRequest) -> OptimizeResponse:
    try:
        result = await run_optimization(req)
        return result
    except ValueError as exc:
        logger.warning("validation_error", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("optimize_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Optimization failed: {exc}",
        )


# ─────────────────────────────────────────────────────────
# GET /routes/{job_id}
# ─────────────────────────────────────────────────────────
@router.get(
    "/routes/{job_id}",
    response_model=OptimizeResponse,
    summary="Retrieve a previous optimization result",
)
async def get_routes(job_id: str) -> OptimizeResponse:
    result = cache.get_job(job_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cached result found for job_id={job_id}. Results are cached for 2 hours.",
        )
    return OptimizeResponse(**result)


# ─────────────────────────────────────────────────────────
# GET /routes  (list last N jobs – from in-process LRU)
# ─────────────────────────────────────────────────────────
@router.get(
    "/routes",
    summary="List recently computed optimization jobs",
)
async def list_routes(limit: int = Query(default=10, ge=1, le=100)) -> dict:
    from app.services.cache import _job_cache   # internal peek
    jobs = list(_job_cache.keys())[-limit:]
    summaries = []
    for jid in jobs:
        data = _job_cache.get(jid, {})
        summaries.append({
            "job_id": jid,
            "status": data.get("status"),
            "total_locations": data.get("total_locations"),
            "assigned_count": data.get("assigned_count"),
            "unassigned_count": data.get("unassigned_count"),
            "vehicles_used": data.get("vehicles_used"),
            "total_distance_km": data.get("total_distance_km"),
            "solver_time_seconds": data.get("solver_time_seconds"),
        })
    return {"count": len(summaries), "jobs": summaries}
