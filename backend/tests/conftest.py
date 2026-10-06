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

from unittest.mock import AsyncMock, MagicMock

import pytest

# Must happen before any ``app.*`` import that constructs Settings:
# ``get_settings`` is lru_cached and ``app.main`` binds it at module scope.
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
