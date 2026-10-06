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

# Must happen before any ``app.*`` import: ``get_settings`` is lru_cached and
# ``app.main`` binds settings at module scope.
from app.config import Settings, get_settings

Settings.model_config["env_file"] = None
get_settings.cache_clear()

TEST_JWT_SECRET = "test-secret-not-for-production-use-only"
