"""
Plan definitions and limit helpers for SaaS subscription tiers.
"""

from __future__ import annotations

from typing import Any

PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "max_optimizations_per_month": 5,
        "max_locations_per_job": 50,
        "allowed_backends": ["haversine"],
        "export_enabled": False,
        "priority_support": False,
        "max_users": 1,
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 4900,  # $49.00 in cents
        "stripe_price_id": "",  # set via env or Stripe dashboard
        "max_optimizations_per_month": 1000,
        "max_locations_per_job": 500,
        "allowed_backends": ["haversine", "osrm", "ors"],
        "export_enabled": True,
        "priority_support": True,
        "max_users": 10,
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 19900,  # $199.00 in cents
        "stripe_price_id": "",
        "max_optimizations_per_month": 10000,
        "max_locations_per_job": 5000,
        "allowed_backends": ["haversine", "osrm", "ors"],
        "export_enabled": True,
        "priority_support": True,
        "max_users": 100,
    },
}


def get_plan_limits(plan: str) -> dict[str, Any]:
    """Return the limits dict for a given plan name. Falls back to 'free'."""
    return PLANS.get(plan, PLANS["free"])


def check_optimization_limit(plan: str, current_month_count: int, n_locations: int, backend: str) -> str | None:
    """Return an error message if the request violates plan limits, else None."""
    limits = get_plan_limits(plan)

    if current_month_count >= limits["max_optimizations_per_month"]:
        return f"Monthly optimization limit ({limits['max_optimizations_per_month']}) reached. Upgrade your plan."

    if n_locations > limits["max_locations_per_job"]:
        return f"Location limit per job ({limits['max_locations_per_job']}) exceeded. Upgrade your plan."

    if backend not in limits["allowed_backends"]:
        allowed = ", ".join(limits["allowed_backends"])
        return f"Routing backend '{backend}' not allowed on your plan. Allowed: {allowed}. Upgrade your plan."

    return None
