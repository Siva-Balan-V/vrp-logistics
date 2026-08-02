"""
Stripe webhook handler.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import Company
from app.services.stripe_service import construct_webhook_event, map_stripe_price_to_plan

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(400, "Missing stripe-signature header")

    event = construct_webhook_event(payload, sig_header)
    if event is None:
        raise HTTPException(400, "Invalid webhook signature")

    event_type = event.get("type")
    logger.info("stripe_webhook_received", type=event_type)

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        company_id = session.get("metadata", {}).get("company_id")
        customer_id = session.get("customer")
        if company_id:
            result = await db.execute(select(Company).where(Company.id == company_id))
            company = result.scalar_one_or_none()
            if company:
                if customer_id:
                    company.stripe_customer_id = customer_id
                line_items = session.get("display_items", [])
                price_id = None
                if line_items:
                    price_id = line_items[0].get("price", {}).get("id")
                if not price_id:
                    # Check subscription data
                    subscription = session.get("subscription")
                    if subscription:
                        import stripe as _stripe

                        from app.config import get_settings

                        _stripe.api_key = get_settings().STRIPE_SECRET_KEY
                        try:
                            sub = _stripe.Subscription.retrieve(subscription)
                            if sub.get("items") and sub["items"].get("data"):
                                price_id = sub["items"]["data"][0].get("price", {}).get("id")
                        except Exception:
                            pass
                plan = map_stripe_price_to_plan(price_id) if price_id else None
                if plan:
                    company.plan = plan
                    logger.info("company_plan_upgraded", company_id=company_id, plan=plan)
                await db.flush()

    elif event_type == "customer.subscription.updated":
        sub = event["data"]["object"]
        customer_id = sub.get("customer")
        if customer_id:
            result = await db.execute(select(Company).where(Company.stripe_customer_id == customer_id))
            company = result.scalar_one_or_none()
            if company:
                items = sub.get("items", {}).get("data", [])
                if items:
                    price_id = items[0].get("price", {}).get("id")
                    plan = map_stripe_price_to_plan(price_id) if price_id else None
                    if plan:
                        company.plan = plan
                        logger.info("company_plan_updated", company_id=str(company.id), plan=plan)
                    await db.flush()

    elif event_type == "customer.subscription.deleted":
        sub = event["data"]["object"]
        customer_id = sub.get("customer")
        if customer_id:
            result = await db.execute(select(Company).where(Company.stripe_customer_id == customer_id))
            company = result.scalar_one_or_none()
            if company:
                company.plan = "free"
                logger.info("company_plan_downgraded", company_id=str(company.id))
                await db.flush()

    return {"status": "ok"}
