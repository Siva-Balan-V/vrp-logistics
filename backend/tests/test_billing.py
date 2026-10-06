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


# ─────────────────────────────────────────────
# POST /api/v1/billing/create-order
# ─────────────────────────────────────────────


class TestCreateOrder:
    def test_rejects_unknown_plan(self, db, billing_client):
        _authenticate(db)
        resp = billing_client.post("/api/v1/billing/create-order?plan=platinum", headers=billing_client.token())
        assert resp.status_code == 400

    def test_rejects_free_plan_upgrade(self, db, billing_client):
        _authenticate(db)
        resp = billing_client.post("/api/v1/billing/create-order?plan=free", headers=billing_client.token())
        assert resp.status_code == 400

    def test_requires_authentication(self, billing_client):
        assert billing_client.post("/api/v1/billing/create-order?plan=pro").status_code == 401

    def test_missing_company_returns_404(self, db, billing_client):
        db.queue(_user(), None)
        resp = billing_client.post("/api/v1/billing/create-order?plan=pro", headers=billing_client.token())
        assert resp.status_code == 404

    def test_unconfigured_razorpay_returns_500(self, db, billing_client):
        _authenticate(db)
        with patch("app.routes.billing.create_order", return_value=None):
            resp = billing_client.post("/api/v1/billing/create-order?plan=pro", headers=billing_client.token())
        assert resp.status_code == 500

    def test_successful_order_returns_provider_id(self, db, billing_client):
        _authenticate(db)
        order = {"order_id": "order_123", "amount": 4900, "currency": "INR", "key_id": "rzp_test"}
        with patch("app.routes.billing.create_order", return_value=order) as mock_create:
            resp = billing_client.post("/api/v1/billing/create-order?plan=pro", headers=billing_client.token())
        assert resp.status_code == 200
        assert resp.json()["order_id"] == "order_123"
        assert mock_create.call_args.kwargs["plan"] == "pro"


# ─────────────────────────────────────────────
# POST /api/v1/billing/verify-payment
# ─────────────────────────────────────────────


class TestBillingFraud:
    """**H1**: the Razorpay signature covers only ``order_id|payment_id``, so
    it says nothing about *which plan* was paid for."""

    def _verify(self, billing_client, plan: str, signature_ok: bool = True):
        params = {
            "razorpay_order_id": "order_123",
            "razorpay_payment_id": "pay_123",
            "razorpay_signature": "sig",
            "plan": plan,
        }
        with patch("app.routes.billing.verify_payment_signature", return_value=signature_ok):
            return billing_client.post(
                "/api/v1/billing/verify-payment",
                params=params,
                headers=billing_client.token(),
            )

    def test_bad_signature_is_rejected(self, db, billing_client):
        company = _company()
        db.queue(_user(), company)
        resp = self._verify(billing_client, plan="enterprise", signature_ok=False)
        assert resp.status_code == 400
        assert company.plan == "free", "a rejected signature must not change the plan"

    def test_unknown_plan_is_rejected(self, db, billing_client):
        company = _company()
        db.queue(_user(), company)
        resp = self._verify(billing_client, plan="platinum")
        assert resp.status_code == 400
        assert company.plan == "free"

    def test_valid_payment_upgrades_plan(self, db, billing_client):
        company = _company()
        db.queue(_user(), company)
        resp = self._verify(billing_client, plan="pro")
        assert resp.status_code == 200
        assert company.plan == "pro"

    def test_records_payment_reference_on_company(self, db, billing_client):
        company = _company()
        db.queue(_user(), company)
        self._verify(billing_client, plan="pro")
        assert company.razorpay_order_id == "order_123"
        assert company.razorpay_payment_id == "pay_123"

    def test_missing_company_returns_404(self, db, billing_client):
        db.queue(_user(), None)
        resp = self._verify(billing_client, plan="pro")
        assert resp.status_code == 404

    def test_client_supplied_enterprise_plan_is_trusted_today(self, db, billing_client):
        """**Documents H1.** A ₹49 `pro` payment replayed with
        ``plan=enterprise`` succeeds: the signature does not bind the plan and
        nothing records the consumption.

        Correct behaviour after PR 1.3: derive the plan from the paid amount
        with ``get_plan_from_razorpay_amount`` and ignore the client's value.
        Flip this test then.
        """
        company = _company()
        db.queue(_user(), company)
        resp = self._verify(billing_client, plan="enterprise")
        assert resp.status_code == 200
        assert company.plan == "enterprise"

    def test_payment_is_replayable_today(self, db, billing_client):
        """**Documents H1.** The same verified triple succeeds repeatedly:
        nothing records that the payment was consumed. After PR 1.3 there must
        be a uniqueness constraint on ``(company_id, razorpay_payment_id)``."""
        company = _company()
        db.queue(_user(), company, _user(), company)
        first = self._verify(billing_client, plan="pro")
        second = self._verify(billing_client, plan="pro")
        assert first.status_code == 200
        assert second.status_code == 200, "documents replay; must become 409 after PR 1.3"


class TestVerifyPaymentSignature:
    """Unit-level checks on the HMAC itself."""

    @staticmethod
    def _sign(order_id: str, payment_id: str, secret: str = "secret") -> str:
        import hashlib
        import hmac

        return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    def test_valid_signature_accepted(self):
        from app.services.razorpay_service import verify_payment_signature

        with patch("app.config.get_settings") as gs:
            gs.return_value.RAZORPAY_KEY_SECRET = "secret"
            assert verify_payment_signature("order_1", "pay_1", self._sign("order_1", "pay_1")) is True

    def test_signature_bound_to_order_and_payment(self):
        from app.services.razorpay_service import verify_payment_signature

        with patch("app.config.get_settings") as gs:
            gs.return_value.RAZORPAY_KEY_SECRET = "secret"
            sig = self._sign("order_1", "pay_1")
            assert verify_payment_signature("order_1", "pay_2", sig) is False
            assert verify_payment_signature("order_2", "pay_1", sig) is False

    def test_unset_secret_rejects_everything(self):
        from app.services.razorpay_service import verify_payment_signature

        with patch("app.config.get_settings") as gs:
            gs.return_value.RAZORPAY_KEY_SECRET = ""
            assert verify_payment_signature("order_1", "pay_1", self._sign("order_1", "pay_1")) is False

    def test_plan_amount_mapping(self):
        from app.services.razorpay_service import get_plan_from_razorpay_amount

        assert get_plan_from_razorpay_amount(4900) == "pro"
        assert get_plan_from_razorpay_amount(19900) == "enterprise"
        assert get_plan_from_razorpay_amount(1) is None


# ─────────────────────────────────────────────
# POST /api/v1/billing/cancel-subscription
# ─────────────────────────────────────────────


class TestBillingAuthorization:
    """**H2**: all billing mutations use ``require_user``, so a plain
    ``member`` can cancel the company subscription. ``api_keys.py`` already
    does this correctly with ``require_admin``."""

    def test_member_cannot_cancel_today(self, db, billing_client):
        """**Documents H2.** A `member` downgrades the company from `pro` to
        `free`. After PR 1.3 this must return 403 and leave the plan alone."""
        company = _company(plan="pro")
        db.queue(_user(role="member"), company)
        resp = billing_client.post("/api/v1/billing/cancel-subscription", headers=billing_client.token())
        assert resp.status_code == 200
        assert company.plan == "free"

    def test_admin_can_cancel(self, db, billing_client):
        company = _company(plan="pro")
        db.queue(_user(role="admin"), company)
        resp = billing_client.post("/api/v1/billing/cancel-subscription", headers=billing_client.token())
        assert resp.status_code == 200
        assert company.plan == "free"

    def test_cancel_requires_authentication(self, billing_client):
        assert billing_client.post("/api/v1/billing/cancel-subscription").status_code == 401

    def test_clears_payment_references(self, db, billing_client):
        company = _company(plan="pro")
        company.razorpay_order_id = "order_123"
        company.razorpay_payment_id = "pay_123"
        db.queue(_user(role="admin"), company)
        billing_client.post("/api/v1/billing/cancel-subscription", headers=billing_client.token())
        assert company.razorpay_order_id is None
        assert company.razorpay_payment_id is None

    def test_missing_company_returns_404(self, db, billing_client):
        db.queue(_user(role="admin"), None)
        resp = billing_client.post("/api/v1/billing/cancel-subscription", headers=billing_client.token())
        assert resp.status_code == 404


# ─────────────────────────────────────────────
# Plan limits
# ─────────────────────────────────────────────


class TestPlanLimits:
    def test_unknown_plan_falls_back_to_free(self):
        from app.services.plans import get_plan_limits

        assert get_plan_limits("enterprise-plus-ultra") == get_plan_limits("free")

    def test_free_plan_blocks_large_jobs(self):
        from app.services.plans import check_optimization_limit

        msg = check_optimization_limit("free", 0, 500, "haversine")
        assert msg is not None and "Location limit" in msg

    def test_free_plan_blocks_paid_backends(self):
        from app.services.plans import check_optimization_limit

        msg = check_optimization_limit("free", 0, 10, "osrm")
        assert msg is not None and "not allowed" in msg

    def test_pro_allows_osrm(self):
        from app.services.plans import check_optimization_limit

        assert check_optimization_limit("pro", 0, 400, "osrm") is None

    def test_monthly_quota_enforced(self):
        from app.services.plans import check_optimization_limit

        msg = check_optimization_limit("free", 5, 10, "haversine")
        assert msg is not None and "Monthly optimization limit" in msg
