"""
Admin-only routes for company and user management.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.db import Company, OptimizationJob, User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/companies")
async def list_companies(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(Company).order_by(Company.created_at.desc()))
    companies = result.scalars().all()
    out = []
    for c in companies:
        user_count = await db.execute(
            select(sa_func.count()).select_from(User).where(User.company_id == c.id)
        )
        job_count = await db.execute(
            select(sa_func.count()).select_from(OptimizationJob).where(OptimizationJob.company_id == c.id)
        )
        out.append({
            "id": str(c.id),
            "name": c.name,
            "plan": c.plan,
            "stripe_customer_id": c.stripe_customer_id,
            "users": user_count.scalar() or 0,
            "optimizations": job_count.scalar() or 0,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return out


@router.get("/companies/{company_id}")
async def get_company_detail(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    users_result = await db.execute(
        select(User).where(User.company_id == company.id).order_by(User.created_at.desc())
    )
    users = [
        {
            "id": str(u.id),
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users_result.scalars().all()
    ]

    job_count = await db.execute(
        select(sa_func.count()).select_from(OptimizationJob).where(OptimizationJob.company_id == company.id)
    )

    return {
        "id": str(company.id),
        "name": company.name,
        "plan": company.plan,
        "stripe_customer_id": company.stripe_customer_id,
        "users": users,
        "total_optimizations": job_count.scalar() or 0,
        "created_at": company.created_at.isoformat() if company.created_at else None,
    }


@router.put("/companies/{company_id}/plan")
async def update_company_plan(
    company_id: str,
    plan: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from app.services.plans import PLANS

    if plan not in PLANS:
        raise HTTPException(400, f"Invalid plan: {plan}. Valid: {', '.join(PLANS.keys())}")

    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    company.plan = plan
    await db.flush()
    logger.info(
        "admin_plan_updated",
        company_id=company_id,
        plan=plan,
        admin_id=str(admin.id),
    )
    return {"id": str(company.id), "name": company.name, "plan": company.plan}
