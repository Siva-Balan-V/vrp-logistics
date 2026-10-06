"""Shared pytest fixtures.

Two jobs:

1. **Environment isolation.** ``app/config.py`` declares ``env_file = ".env"``,
   so pydantic-settings reads ``backend/.env`` at import time. A developer
   ``.env`` carrying a ``DATABASE_URL`` pointing at a database that is not
   running makes the app lifespan call ``wait_for_db`` (10 retries x 2s) and
   then ``run_migrations`` on every ``TestClient`` construction. The suite
   stalls for many minutes instead of failing. CI has no ``.env``, so this
   never shows up there. Disabling the env file for the session fixes it and
   makes tests independent of the developer's working copy.

2. **Reusable auth and app fixtures**, so the auth and billing suites can
   assert on *rejections* rather than only on happy paths.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Must happen before any ``app.*`` import: ``get_settings`` is lru_cached and
# ``app.main`` binds settings at module scope.
from app.config import Settings, get_settings

Settings.model_config["env_file"] = None
get_settings.cache_clear()

TEST_JWT_SECRET = "test-secret-not-for-production-use-only"


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Settings with a known JWT secret, so token tests are deterministic."""
    return Settings(
        _env_file=None,
        JWT_SECRET_KEY=TEST_JWT_SECRET,
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
        JWT_REFRESH_TOKEN_EXPIRE_DAYS=7,
    )


@pytest.fixture
def db_mock() -> AsyncMock:
    """A mock AsyncSession whose single scalar result can be set per test."""
    db = AsyncMock()
    result = MagicMock()
    db.execute.return_value = result
    db.scalar_one_or_none.return_value = None
    db.scalars.return_value.all.return_value = []
    return db


@pytest.fixture
def db_dependency(db_mock):
    """Override ``get_db`` with ``db_mock`` and clear overrides afterwards."""
    from app.database import get_db

    async def _fake_db():
        yield db_mock

    def _install(app):
        app.dependency_overrides[get_db] = _fake_db
        return app

    yield _install
    # Overrides are cleared by the app fixture that requested them.


@pytest.fixture
def make_user():
    """Factory for a User row with sane defaults.

    ``password_hash`` is a precomputed bcrypt hash of ``correct-horse`` so
    ``verify_password`` has something real to check without paying bcrypt's
    cost on every test.
    """

    def _factory(
        *,
        email: str = "user@example.com",
        company_id: uuid.UUID | str = "00000000-0000-0000-0000-000000000002",
        role: str = "member",
        is_active: bool = True,
        with_company: bool = True,
    ):
        from app.models.db import Company, User

        company = None
        if with_company:
            cid = company_id if isinstance(company_id, uuid.UUID) else uuid.UUID(str(company_id))
            company = Company(id=cid, name="Test Co")
        return User(
            id=uuid.uuid4(),
            email=email,
            password_hash="$2b$12$abcdefghijklmnopqrstuvCPMvIQfMXvVBGMPvhO3BsS0lACz3ZK1fEa",
            company_id=company.id if company else company_id,
            role=role,
            is_active=is_active,
            created_at=datetime.now(UTC),
            company=company,
        )

    return _factory


@pytest.fixture
def access_token(settings):
    """Build an access token signed with the test secret."""
    from app.services.auth import create_access_token

    def _factory(user_id, **extra):
        return create_access_token({"sub": str(user_id), **extra})

    return _factory


@pytest.fixture
def auth_headers(access_token):
    """Factory for an ``Authorization`` header for a given user id."""

    def _factory(user_id, token_type: str = "access") -> dict[str, str]:
        if token_type == "refresh":
            from app.services.auth import create_refresh_token

            token = create_refresh_token({"sub": str(user_id)})
        else:
            token = access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    return _factory


@pytest.fixture
def app():
    """A fresh application with dependency overrides cleared on teardown."""
    from app.main import create_app

    instance = create_app()
    yield instance
    instance.dependency_overrides.clear()


@pytest.fixture
def client(app, db_dependency):
    """TestClient wired to ``db_mock`` via ``get_db``."""
    db_dependency(app)
    with TestClient(app) as c:
        yield c
