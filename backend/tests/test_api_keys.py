"""Tests for API key generation, authentication, and management endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies import ApiKeyPrincipal, get_current_principal, require_permission
from app.main import create_app
from app.models.db import ApiKey
from app.models.schemas import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.services import api_keys

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _make_key(active: bool = True, expires_at: datetime | None = None) -> ApiKey:
    return ApiKey(
        id=uuid.uuid4(),
        company_id=_COMPANY_ID,
        name="test-key",
        key_hash="a" * 64,
        prefix="rf_abcd1234",
        permissions=["optimize", "read"],
        is_active=active,
        expires_at=expires_at,
        created_at=datetime.now(UTC),
    )


def _mock_db(key: ApiKey | None = None, keys: list | None = None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    db.execute.return_value = result
    result.scalar_one_or_none.return_value = key
    if keys is not None:
        result.scalars.return_value.all.return_value = keys
    return db


class TestGenerateApiKey:
    def test_format_and_prefix(self):
        full, prefix, key_hash = api_keys.generate_api_key()
        assert full.startswith(api_keys.API_KEY_PREFIX)
        assert prefix == full[:12]
        assert len(key_hash) == 64

    def test_unique(self):
        keys = {api_keys.generate_api_key()[0] for _ in range(50)}
        assert len(keys) == 50

    def test_hash_deterministic(self):
        assert api_keys.hash_api_key("rf_abc") == api_keys.hash_api_key("rf_abc")
        assert api_keys.hash_api_key("rf_abc") != api_keys.hash_api_key("rf_abd")


class TestAuthenticateApiKey:
    async def test_valid_key_updates_last_used(self):
        key = _make_key()
        db = _mock_db(key=key)
        result = await api_keys.authenticate_api_key(db, "rf_validkey")
        assert result is key
        assert key.last_used_at is not None
        db.commit.assert_awaited_once()

    async def test_unknown_key_returns_none(self):
        db = _mock_db(key=None)
        assert await api_keys.authenticate_api_key(db, "rf_unknown") is None

    async def test_expired_key_returns_none(self):
        key = _make_key(expires_at=datetime.now(UTC) - timedelta(days=1))
        db = _mock_db(key=key)
        assert await api_keys.authenticate_api_key(db, "rf_expired") is None


class TestCreateApiKeyService:
    async def test_persists_and_returns_plaintext(self):
        db = _mock_db()
        db.add = MagicMock()
        key, plaintext = await api_keys.create_api_key(db, _COMPANY_ID, "Prod", ["optimize"], None)
        assert plaintext.startswith(api_keys.API_KEY_PREFIX)
        assert key.key_hash == api_keys.hash_api_key(plaintext)
        assert key.prefix == plaintext[:12]
        assert key.is_active is True
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()


class TestGetCurrentPrincipal:
    async def test_api_key_header_wins(self):
        key = _make_key()
        db = _mock_db(key=key)
        with patch("app.dependencies.is_db_enabled", lambda: True):
            principal = await get_current_principal(x_api_key="rf_validkey", credentials=None, db=db)
        assert isinstance(principal, ApiKeyPrincipal)
        assert principal.company_id == _COMPANY_ID
        assert principal.api_key is key

    async def test_invalid_api_key_raises_401(self):
        db = _mock_db(key=None)
        with patch("app.dependencies.is_db_enabled", lambda: True), pytest.raises(HTTPException) as exc:
            await get_current_principal(x_api_key="rf_bad", credentials=None, db=db)
        assert exc.value.status_code == 401


class TestRequirePermission:
    async def test_api_key_missing_permission_denied(self):
        key = _make_key()
        key.permissions = ["read"]
        principal = ApiKeyPrincipal(company_id=_COMPANY_ID, api_key=key)
        with pytest.raises(HTTPException) as exc:
            await require_permission("optimize")(principal)
        assert exc.value.status_code == 403

    async def test_api_key_with_permission_allowed(self):
        key = _make_key()
        principal = ApiKeyPrincipal(company_id=_COMPANY_ID, api_key=key)
        out = await require_permission("optimize")(principal)
        assert out is principal

    async def test_user_always_passes(self):
        user = MagicMock()
        out = await require_permission("optimize")(user)
        assert out is user


class TestSchemas:
    def test_create_schema_defaults(self):
        body = ApiKeyCreate(name="Prod")
        assert body.permissions == ["optimize", "read"]
        assert body.expires_at is None

    def test_created_response(self):
        resp = ApiKeyCreatedResponse(
            id=str(_COMPANY_ID),
            name="Prod",
            prefix="rf_abcd1234",
            permissions=["optimize"],
            is_active=True,
            key="rf_secret",
        )
        assert resp.key == "rf_secret"

    def test_key_not_in_response_model(self):
        fields = ApiKeyResponse.model_fields
        assert "key" not in fields


class TestRoutes:
    @pytest.fixture
    def app_and_state(self):
        from app.database import get_db

        app = create_app()
        mock_user = MagicMock()
        mock_user.company_id = _COMPANY_ID
        from app.dependencies import require_admin

        app.dependency_overrides[require_admin] = lambda: mock_user

        state = {"db": AsyncMock()}

        async def _fake_db():
            yield state["db"]

        app.dependency_overrides[get_db] = _fake_db
        with patch("app.routes.api_keys.is_db_enabled", lambda: True), TestClient(app) as c:
            yield c, state
        app.dependency_overrides.clear()

    def test_list_keys(self, app_and_state):
        c, state = app_and_state
        key = _make_key()
        state["db"].execute.return_value = MagicMock()
        state["db"].execute.return_value.scalars.return_value.all.return_value = [key]
        resp = c.get("/api/v1/api-keys")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(key.id)
        assert data[0]["prefix"] == key.prefix

    def test_create_key_returns_plaintext_once(self, app_and_state):
        c, state = app_and_state
        key = _make_key()

        async def fake_create(db, company_id, name, permissions, expires_at):
            return key, "rf_plaintextsecret"

        with patch("app.routes.api_keys.create_api_key", side_effect=fake_create):
            resp = c.post("/api/v1/api-keys", json={"name": "Prod"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"] == "rf_plaintextsecret"
        assert data["id"] == str(key.id)
        assert data["permissions"] == ["optimize", "read"]

    def test_create_key_invalid_permission_rejected(self, app_and_state):
        c, _ = app_and_state
        resp = c.post("/api/v1/api-keys", json={"name": "x", "permissions": ["admin"]})
        assert resp.status_code == 422

    def test_revoke_key(self, app_and_state):
        c, state = app_and_state
        key = _make_key(active=True)
        state["db"].execute.return_value = MagicMock()
        state["db"].execute.return_value.scalar_one_or_none.return_value = key
        resp = c.delete(f"/api/v1/api-keys/{key.id}")
        assert resp.status_code == 200
        assert key.is_active is False
        state["db"].commit.assert_awaited_once()

    def test_revoke_unknown_key_404(self, app_and_state):
        c, state = app_and_state
        state["db"].execute.return_value = MagicMock()
        state["db"].execute.return_value.scalar_one_or_none.return_value = None
        resp = c.delete("/api/v1/api-keys/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_db_disabled_returns_503(self):
        from app.database import get_db
        from app.dependencies import require_admin

        app = create_app()
        mock_user = MagicMock()
        mock_user.company_id = _COMPANY_ID
        app.dependency_overrides[require_admin] = lambda: mock_user

        state = {"db": AsyncMock()}

        async def _fake_db():
            yield state["db"]

        app.dependency_overrides[get_db] = _fake_db
        with patch("app.routes.api_keys.is_db_enabled", lambda: False), TestClient(app) as c:
            resp = c.get("/api/v1/api-keys")
        assert resp.status_code == 503
        app.dependency_overrides.clear()
