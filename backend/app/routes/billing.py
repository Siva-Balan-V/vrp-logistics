"""
Billing and subscription management routes.
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
from app.models.schemas import PlanInfo
from app.services.plans import PLANS, get_plan_limits
from app.services.stripe_service import (
    create_checkout_session,
    create_portal_session,
    get_or_create_customer,
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


@router.post("/create-checkout")
async def create_checkout(
    plan: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Create a Stripe checkout session for upgrading/downgrading."""
    settings = get_settings()
    price_id = None
    if plan == "pro":
        price_id = settings.STRIPE_PRICE_PRO
    elif plan == "enterprise":
        price_id = settings.STRIPE_PRICE_ENTERPRISE
    else:
        raise HTTPException(400, f"Invalid plan: {plan}")

    if not price_id:
        raise HTTPException(400, "Stripe price not configured for this plan")

    company_result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    customer_id = await get_or_create_customer(
        str(company.id), company.name, user.email
    )
    if customer_id:
        company.stripe_customer_id = customer_id
        await db.flush()

    base = str(settings.ALLOWED_ORIGINS[0]) if settings.ALLOWED_ORIGINS else "http://localhost:5173"
    session = await create_checkout_session(
        company_id=str(company.id),
        company_name=company.name,
        price_id=price_id,
        success_url=f"{base}/billing?success=1",
        cancel_url=f"{base}/billing?canceled=1",
        customer_id=customer_id,
    )
    if not session:
        raise HTTPException(500, "Failed to create checkout session")
    return session


@router.post("/portal")
async def customer_portal(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Create a Stripe Customer Portal session for managing subscription."""
    company_result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = company_result.scalar_one_or_none()
    if not company or not company.stripe_customer_id:
        raise HTTPException(400, "No Stripe customer found")

    settings = get_settings()
    base = str(settings.ALLOWED_ORIGINS[0]) if settings.ALLOWED_ORIGINS else "http://localhost:5173"
    url = await create_portal_session(company.stripe_customer_id, f"{base}/billing")
    if not url:
        raise HTTPException(500, "Failed to create portal session")
    return {"url": url}
