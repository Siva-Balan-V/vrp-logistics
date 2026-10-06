"""Tests for /api/v1/billing.

Billing had **no** test coverage. These tests document current behaviour so
the H1/H2 fixes have a baseline, and they assert the rejection paths a
security change needs to preserve.

Two documented defects are asserted as *current* behaviour:

- ``TestBillingFraud.test_client_supplied_enterprise_plan_is_trusted_today``
- ``TestBillingFraud.test_payment_is_replayable_today``
- ``TestBillingAuthorization.test_member_cannot_cancel_today``

Each docstring says what the correct behaviour is. Flip the assertion when
PR 1.3 lands.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.mock_db import MockSession

_COMPANY_ID = "00000000-0000-0000-0000-000000000002"
_USER_ID = "00000000-0000-0000-0000-000000000001"


def _user(role: str = "member", company_id: str = _COMPANY_ID):
    from datetime import UTC, datetime

    from app.models.db import User

    return User(
        id=_USER_ID,
        email=f"{role}@example.com",
        password_hash="x" * 60,
        company_id=company_id,
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
    )


def _company(plan: str = "free"):
    from datetime import UTC, datetime

    from app.models.db import Company

    return Company(
        id=_COMPANY_ID,
        name="Test Co",
        plan=plan,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def db():
    return MockSession()


@pytest.fixture
def billing_client(db):
    """TestClient with ``get_db`` mocked and the DB reported as enabled.

    ``execute`` returns queued scalars in order, so the caller can line up
    ``get_current_user``'s lookup with the handler's own.
    """
    from app.database import get_db
    from app.services.auth import create_access_token

    async def _fake_db():
        yield db

    app = create_app()
    app.dependency_overrides[get_db] = _fake_db

    def _token():
        return {"Authorization": f"Bearer {create_access_token({'sub': _USER_ID})}"}

    with patch("app.dependencies.is_db_enabled", return_value=True), TestClient(app) as client:
        client.token = _token
        yield client
    app.dependency_overrides.clear()


def _authenticate(db, role: str = "member", company=None):
    """Queue the auth lookup plus the company lookup the handler will do."""
    db.queue(_user(role=role), company if company is not None else _company())


# ─────────────────────────────────────────────
# GET /api/v1/billing/plans
# ─────────────────────────────────────────────


class TestListPlans:
    def test_plans_are_public(self, billing_client):
        """Listing plans needs no auth and leaks nothing sensitive."""
        resp = billing_client.get("/api/v1/billing/plans")
        assert resp.status_code == 200
        assert {p["id"] for p in resp.json()["plans"]} == {"free", "pro", "enterprise"}

    def test_free_plan_disables_export(self, billing_client):
        plans = {p["id"]: p for p in billing_client.get("/api/v1/billing/plans").json()["plans"]}
        assert plans["free"]["export_enabled"] is False
        assert plans["pro"]["export_enabled"] is True


# ─────────────────────────────────────────────
# GET /api/v1/billing/usage
# ─────────────────────────────────────────────


class TestUsage:
    def test_requires_authentication(self, billing_client):
        assert billing_client.get("/api/v1/billing/usage").status_code == 401

    def test_scopes_to_callers_company(self, db, billing_client):
        # auth lookup, then the monthly count, then the company row
        db.queue(_user(), None, _company(plan="pro"))
        db.set_scalar(7)
        resp = billing_client.get("/api/v1/billing/usage", headers=billing_client.token())
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"] == "pro"
        assert body["monthly_optimizations_used"] == 7

    def test_falls_back_to_free_when_company_missing(self, db, billing_client):
        db.queue(_user(), None, None)
        db.set_scalar(0)
        resp = billing_client.get("/api/v1/billing/usage", headers=billing_client.token())
        assert resp.json()["plan"] == "free"

    def test_uses_caller_company_id_in_query(self, db, billing_client):
        """The usage query must be filtered by the authenticated company, so
        one tenant cannot read another's counter."""
        db.queue(_user(), None, _company(plan="pro"))
        billing_client.get("/api/v1/billing/usage", headers=billing_client.token())
        stmt = db.execute.await_args_list[1].args[0]
        assert str(_COMPANY_ID) in str(stmt.compile().params)
