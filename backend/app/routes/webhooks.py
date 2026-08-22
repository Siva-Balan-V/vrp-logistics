"""
Razorpay webhook handler.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import Company
from app.services.razorpay_service import get_plan_from_razorpay_amount, verify_webhook_signature

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    if not signature:
        raise HTTPException(400, "Missing x-razorpay-signature header")

    if not verify_webhook_signature(payload, signature):
        raise HTTPException(400, "Invalid webhook signature")

    try:
        event = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload") from None

    event_type = event.get("event")
    logger.info("razorpay_webhook_received", type=event_type)

    if event_type == "payment.captured":
        payload_data = event.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payload_data.get("order_id")
        amount = payload_data.get("amount")
        notes = payload_data.get("notes", {})
        company_id = notes.get("company_id")

        if company_id and amount:
            plan = get_plan_from_razorpay_amount(amount)
            if plan:
                result = await db.execute(select(Company).where(Company.id == company_id))
                company = result.scalar_one_or_none()
                if company:
                    company.plan = plan
                    company.razorpay_order_id = order_id
                    company.razorpay_payment_id = payload_data.get("id")
                    await db.flush()
                    logger.info(
                        "company_plan_upgraded_via_webhook",
                        company_id=company_id,
                        plan=plan,
                    )

    elif event_type == "payment.failed":
        payload_data = event.get("payload", {}).get("payment", {}).get("entity", {})
        notes = payload_data.get("notes", {})
        company_id = notes.get("company_id")
        if company_id:
            logger.warning("payment_failed", company_id=company_id)

    return {"status": "ok"}
