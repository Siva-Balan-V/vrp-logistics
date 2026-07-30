"""
Stripe integration for subscription management.
Handles checkout sessions, customer management, and webhook events.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def get_stripe():
    """Lazy-import stripe and set the API key."""
    import stripe as _stripe
    from app.config import get_settings
    _stripe.api_key = get_settings().STRIPE_SECRET_KEY
    return _stripe


async def create_checkout_session(
    company_id: str,
    company_name: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    customer_id: str | None = None,
) -> dict | None:
    """Create a Stripe checkout session for a subscription."""
    stripe = get_stripe()
    if not stripe.api_key:
        logger.warning("stripe_not_configured")
        return None

    try:
        params = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"company_id": company_id},
            "client_reference_id": company_id,
        }
        if customer_id:
            params["customer"] = customer_id
        else:
            params["customer_email"] = None  # collected at checkout

        session = stripe.checkout.Session.create(**params)
        logger.info("stripe_checkout_created", session_id=session.id, company_id=company_id)
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error("stripe_checkout_failed", error=str(e))
        return None


async def create_portal_session(
    customer_id: str, return_url: str
) -> str | None:
    """Create a Stripe Customer Portal session for managing subscription."""
    stripe = get_stripe()
    if not stripe.api_key:
        return None
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url
    except Exception as e:
        logger.error("stripe_portal_failed", error=str(e))
        return None


async def get_or_create_customer(company_id: str, company_name: str, email: str) -> str | None:
    """Get existing Stripe customer or create a new one."""
    stripe = get_stripe()
    if not stripe.api_key:
        return None
    try:
        customers = stripe.Customer.list(metadata={"company_id": company_id}, limit=1)
        if customers.data:
            return customers.data[0].id

        customer = stripe.Customer.create(
            metadata={"company_id": company_id},
            name=company_name,
            email=email,
        )
        logger.info("stripe_customer_created", customer_id=customer.id, company_id=company_id)
        return customer.id
    except Exception as e:
        logger.error("stripe_customer_failed", error=str(e))
        return None


def map_stripe_price_to_plan(price_id: str) -> str | None:
    """Map a Stripe price ID to a plan name."""
    from app.config import get_settings
    settings = get_settings()
    mapping = {
        settings.STRIPE_PRICE_PRO: "pro",
        settings.STRIPE_PRICE_ENTERPRISE: "enterprise",
    }
    return mapping.get(price_id)


def construct_webhook_event(payload: bytes, sig_header: str) -> dict | None:
    """Verify and construct a Stripe webhook event."""
    from app.config import get_settings
    settings = get_settings()
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("stripe_webhook_secret_not_set")
        return None
    stripe = get_stripe()
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        return event
    except Exception as e:
        logger.error("stripe_webhook_verification_failed", error=str(e))
        return None
