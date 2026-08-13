"""Tests for the tenant-propagation fix in auth dependencies.

`get_current_user` must eager-load the `User.company` relationship so that
`GET /api/v1/auth/me` (which reads ``user.company.name``) does not trigger an
async lazy-load outside of the session (MissingGreenlet).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, require_user
from app.main import create_app
from app.models.db import Company, User
from app.services.auth import create_access_token

_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _make_user(company: Company | None = None) -> User:
    return User(
        id=_USER_ID,
        email="test@example.com",
        password_hash="x" * 60,
        company_id=_COMPANY_ID,
        role="member",
        is_active=True,
        created_at=datetime.now(UTC),
        company=company,
    )


class TestGetCurrentUser:
    @pytest.fixture(autouse=True)
    def _patch_token(self):
        with patch("app.dependencies.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": str(_USER_ID), "type": "access"}
            yield

    @pytest.fixture
    def user(self):
        return _make_user(Company(id=_COMPANY_ID, name="Test Co"))

    @pytest.fixture
    def db(self, user):
        db = AsyncMock()
        result = MagicMock()
        db.execute.return_value = result
        result.scalar_one_or_none.return_value = user
        return db

    async def test_loads_company_via_selectinload(self, db):
        with patch("app.dependencies.is_db_enabled", lambda: True):
            result = await get_current_user(credentials=MagicMock(credentials="token"), db=db)
        assert result is not None
        stmt = db.execute.await_args.args[0]
        load = stmt._with_options[0].context[0]
        assert str(load.path) == ("ORM Path[Mapper[User(users)] -> User.company -> Mapper[Company(companies)]]")
        assert load.strategy == (("lazy", "selectin"),)

    async def test_returns_none_when_db_disabled(self, db):
        with patch("app.dependencies.is_db_enabled", lambda: False):
            result = await get_current_user(credentials=MagicMock(credentials="token"), db=db)
        assert result is None
        db.execute.assert_not_awaited()

    async def test_invalid_token_raises_401(self, db):
        with (
            patch("app.dependencies.is_db_enabled", lambda: True),
            patch("app.dependencies.decode_token", return_value=None),
            pytest.raises(HTTPException) as exc,
        ):
            await get_current_user(credentials=MagicMock(credentials="bad"), db=db)
        assert exc.value.status_code == 401

    async def test_missing_user_raises_401(self, db):
        db.execute.return_value.scalar_one_or_none.return_value = None
        with patch("app.dependencies.is_db_enabled", lambda: True), pytest.raises(HTTPException) as exc:
            await get_current_user(credentials=MagicMock(credentials="token"), db=db)
        assert exc.value.status_code == 401

    async def test_require_user_passes(self, user):
        with patch("app.dependencies.is_db_enabled", lambda: True):
            out = await require_user(user)
        assert out is user

    async def test_require_user_none_raises(self):
        with pytest.raises(HTTPException) as exc:
            await require_user(None)
        assert exc.value.status_code == 401


class TestMeEndpoint:
    """End-to-end: GET /api/v1/auth/me must return company_name from the relationship."""

    @pytest.fixture
    def app_and_state(self):
        from app.database import get_db

        app = create_app()
        user = _make_user(Company(id=_COMPANY_ID, name="Test Co"))
        state = {"db": AsyncMock(), "user": user}
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        state["db"].execute.return_value = result

        async def _fake_db():
            yield state["db"]

        app.dependency_overrides[get_db] = _fake_db
        with patch("app.dependencies.is_db_enabled", lambda: True), TestClient(app) as c:
            yield c, state
        app.dependency_overrides.clear()

    def test_me_returns_company_name(self, app_and_state):
        c, state = app_and_state
        token = create_access_token({"sub": str(_USER_ID)})
        resp = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_id"] == str(_COMPANY_ID)
        assert data["company_name"] == "Test Co"
        assert data["email"] == "test@example.com"

    def test_me_returns_empty_company_name_without_company(self, app_and_state):
        c, state = app_and_state
        state["user"].company = None
        token = create_access_token({"sub": str(_USER_ID)})
        resp = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["company_name"] == ""
