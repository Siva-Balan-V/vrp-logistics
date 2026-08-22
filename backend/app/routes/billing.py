"""
Billing and subscription management routes (Razorpay).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_user
from app.models.db import Company, OptimizationJob, User
from app.services.plans import PLANS, get_plan_limits
from app.services.razorpay_service import (
    create_order,
    verify_payment_signature,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/plans")
async def list_plans():
    """Return available subscription plans with pricing."""
    return {
        "plans": [
            {
                "id": key,
                "name": info["name"],
                "price_monthly": info["price_monthly"],
                "max_optimizations_per_month": info["max_optimizations_per_month"],
                "max_locations_per_job": info["max_locations_per_job"],
                "allowed_backends": info["allowed_backends"],
                "export_enabled": info["export_enabled"],
                "priority_support": info["priority_support"],
                "max_users": info["max_users"],
            }
            for key, info in PLANS.items()
        ]
    }


@router.get("/usage")
async def get_usage(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Return current billing period usage for the company."""
    from sqlalchemy import func as sa_func

    result = await db.execute(
        select(sa_func.count())
        .select_from(OptimizationJob)
        .where(
            OptimizationJob.company_id == user.company_id,
            OptimizationJob.created_at >= sa_func.date_trunc("month", sa_func.now()),
        )
    )
    month_count = result.scalar() or 0

    company_result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = company_result.scalar_one_or_none()
    plan = company.plan if company else "free"
    limits = get_plan_limits(plan)

    return {
        "plan": plan,
        "monthly_optimizations_used": month_count,
        "monthly_optimizations_limit": limits["max_optimizations_per_month"],
        "max_locations_per_job": limits["max_locations_per_job"],
        "allowed_backends": limits["allowed_backends"],
        "export_enabled": limits["export_enabled"],
        "max_users": limits["max_users"],
        "users_count": None,
    }


@router.post("/create-order")
async def create_razorpay_order(
    plan: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Create a Razorpay order for upgrading/downgrading."""
    if plan not in ("pro", "enterprise"):
        raise HTTPException(400, f"Invalid plan: {plan}")

    company_result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    settings = get_settings()
    base = str(settings.ALLOWED_ORIGINS[0]) if settings.ALLOWED_ORIGINS else "http://localhost:5173"

    order = create_order(
        company_id=str(company.id),
        plan=plan,
        success_url=f"{base}/billing?success=1",
        cancel_url=f"{base}/billing?canceled=1",
    )
    if not order:
        raise HTTPException(500, "Failed to create Razorpay order. Check Razorpay credentials.")

    return order


@router.post("/verify-payment")
async def verify_razorpay_payment(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    plan: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Verify Razorpay payment and upgrade company plan."""
    is_valid = verify_payment_signature(
        order_id=razorpay_order_id,
        payment_id=razorpay_payment_id,
        signature=razorpay_signature,
    )
    if not is_valid:
        raise HTTPException(400, "Payment signature verification failed")

    if plan not in ("pro", "enterprise"):
        raise HTTPException(400, f"Invalid plan: {plan}")

    company_result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    company.plan = plan
    company.razorpay_order_id = razorpay_order_id
    company.razorpay_payment_id = razorpay_payment_id
    await db.flush()

    logger.info(
        "razorpay_payment_verified",
        company_id=str(company.id),
        plan=plan,
        order_id=razorpay_order_id,
        payment_id=razorpay_payment_id,
    )

    return {
        "status": "success",
        "plan": plan,
        "message": f"Upgraded to {plan} plan successfully",
    }


@router.post("/cancel-subscription")
async def cancel_subscription(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Downgrade company to free plan."""
    company_result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    company.plan = "free"
    company.razorpay_order_id = None
    company.razorpay_payment_id = None
    await db.flush()

    logger.info("subscription_cancelled", company_id=str(company.id))
    return {"status": "success", "plan": "free"}
