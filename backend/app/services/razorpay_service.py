"""
Razorpay integration for subscription management.
Handles order creation, payment verification, and webhook events.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import structlog

logger = structlog.get_logger(__name__)

# Razorpay plan amounts (in INR paise)
RAZORPAY_PLANS = {
    "pro": {
        "amount": 4900,  # ₹49.00
        "currency": "INR",
        "interval": 1,
        "period": "monthly",
    },
    "enterprise": {
        "amount": 19900,  # ₹199.00
        "currency": "INR",
        "interval": 1,
        "period": "monthly",
    },
}


def get_client():
    """Lazy-import razorpay and return a client instance."""
    import razorpay as _razorpay

    from app.config import get_settings

    settings = get_settings()
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        logger.warning("razorpay_not_configured")
        return None

    return _razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_order(company_id: str, plan: str, success_url: str, cancel_url: str) -> dict | None:
    """Create a Razorpay order for a subscription upgrade."""
    client = get_client()
    if not client:
        return None

    plan_info = RAZORPAY_PLANS.get(plan)
    if not plan_info:
        logger.error("razorpay_invalid_plan", plan=plan)
        return None

    try:
        order = client.order.create(
            {
                "amount": plan_info["amount"],
                "currency": plan_info["currency"],
                "receipt": f"rf_{company_id[:8]}_{plan}_{int(time.time())}",
                "notes": {
                    "company_id": company_id,
                    "plan": plan,
                },
            }
        )
        logger.info(
            "razorpay_order_created",
            order_id=order["id"],
            company_id=company_id,
            plan=plan,
        )
        return {
            "order_id": order["id"],
            "amount": plan_info["amount"],
            "currency": plan_info["currency"],
            "key_id": client.auth[0],
            "company_id": company_id,
            "plan": plan,
        }
    except Exception as e:
        logger.error("razorpay_order_failed", error=str(e), company_id=company_id)
        return None


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature using HMAC SHA256."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.RAZORPAY_KEY_SECRET:
        logger.warning("razorpay_secret_not_set")
        return False

    try:
        payload = f"{order_id}|{payment_id}"
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        is_valid = hmac.compare_digest(expected, signature)
        if not is_valid:
            logger.error("razorpay_signature_mismatch", order_id=order_id)
        return is_valid
    except Exception as e:
        logger.error("razorpay_signature_verification_failed", error=str(e))
        return False


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify Razorpay webhook signature."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        logger.warning("razorpay_webhook_secret_not_set")
        return False

    try:
        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error("razorpay_webhook_verification_failed", error=str(e))
        return False


def get_plan_from_razorpay_amount(amount: int) -> str | None:
    """Map a Razorpay amount (in paise) to a plan name."""
    for plan_name, plan_info in RAZORPAY_PLANS.items():
        if plan_info["amount"] == amount:
            return plan_name
    return None
