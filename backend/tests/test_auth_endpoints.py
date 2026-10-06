"""Endpoint tests for /api/v1/auth.

These are the first tests to cover the auth routes. They lock in the
*rejection* paths as well as the happy path, because the auth boundary is
what the billing and admin fixes depend on.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.main import create_app
from app.models.db import Company, User

_USER_ID = "00000000-0000-0000-0000-000000000001"
_COMPANY_ID = "00000000-0000-0000-0000-000000000002"


def _db_returning(user):
    """AsyncMock session whose first scalar result is ``user``."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result
    return db


def _user(**overrides):
    from datetime import UTC, datetime

    defaults = {
        "id": _USER_ID,
        "email": "user@example.com",
        "password_hash": "$2b$12$abcdefghijklmnopqrstuvCPMvIQfMXvVBGMPvhO3BsS0lACz3ZK1fEa",
        "company_id": _COMPANY_ID,
        "role": "member",
        "is_active": True,
        "created_at": datetime.now(UTC),
        "company": Company(id=_COMPANY_ID, name="Test Co"),
    }
    defaults.update(overrides)
    return User(**defaults)


@pytest.fixture
def db_enabled():
    """Force the auth routes to believe a database is configured."""
    with patch("app.routes.auth.is_db_enabled", return_value=True):
        yield


@pytest.fixture
def client_with_db(db_mock, db_enabled):
    from app.database import get_db

    app = create_app()

    async def _fake_db():
        yield db_mock

    app.dependency_overrides[get_db] = _fake_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────
# Token type separation
# ─────────────────────────────────────────────


class TestTokenTypes:
    """An access token must never be usable where a refresh token is expected,
    and vice versa. `decode_token` gates on the ``type`` claim."""

    def test_refresh_rejects_access_token(self):
        from app.services.auth import create_access_token, decode_token

        assert decode_token(create_access_token({"sub": _USER_ID}), expected_type="refresh") is None

    def test_access_rejects_refresh_token(self):
        from app.services.auth import create_refresh_token, decode_token

        assert decode_token(create_refresh_token({"sub": _USER_ID}), expected_type="access") is None

    def test_decode_accepts_matching_type(self):
        from app.services.auth import create_access_token, decode_token

        payload = decode_token(create_access_token({"sub": _USER_ID}), expected_type="access")
        assert payload is not None
        assert payload["sub"] == _USER_ID

    def test_decode_rejects_garbage(self):
        from app.services.auth import decode_token

        assert decode_token("not-a-jwt") is None

    def test_tampered_signature_rejected(self):
        from app.services.auth import create_access_token, decode_token

        token = create_access_token({"sub": _USER_ID})
        tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
        assert decode_token(tampered) is None
