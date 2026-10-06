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


# ─────────────────────────────────────────────
# Password hashing
# ─────────────────────────────────────────────


class TestPasswordHashing:
    """`hash_password` / `verify_password` had no coverage at all, which is
    what blocked the passlib -> bcrypt migration."""

    def test_hash_then_verify_roundtrip(self):
        from app.services.auth import hash_password, verify_password

        hashed = hash_password("correct-horse-battery-staple")
        assert hashed != "correct-horse-battery-staple"
        assert verify_password("correct-horse-battery-staple", hashed) is True

    def test_verify_rejects_wrong_password(self):
        from app.services.auth import hash_password, verify_password

        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_is_salted(self):
        from app.services.auth import hash_password

        assert hash_password("same-password") != hash_password("same-password")

    def test_verify_password_raises_on_malformed_hash(self):
        """Documents a real defect rather than asserting the correct behaviour.

        ``verify_password`` propagates ``passlib.exc.UnknownHashError`` instead
        of returning False. ``authenticate_user`` calls it unguarded, so one
        corrupt ``password_hash`` column turns login into a 500 rather than a
        401 — and enumerates which emails exist.

        Not yet in the roadmap. Fix is to catch ``ValueError``/``Exception``
        inside ``verify_password`` and return False; flip this test to assert
        ``is False`` at that point.
        """
        import pytest

        from app.services.auth import verify_password

        with pytest.raises(Exception, match="hash could not be identified"):
            verify_password("anything", "not-a-bcrypt-hash")


# ─────────────────────────────────────────────
# POST /api/v1/auth/register
# ─────────────────────────────────────────────


class TestRegister:
    def test_returns_201_with_both_token_types(self, client_with_db):
        with patch("app.routes.auth.register_user", AsyncMock(return_value=_user())) as reg:
            resp = client_with_db.post(
                "/api/v1/auth/register",
                json={"email": "user@example.com", "password": "password123", "company_name": "Test Co"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["access_token"] and body["refresh_token"]
        assert reg.await_args is not None

    def test_company_name_signup_gets_admin_role(self, client_with_db):
        """Documented behaviour, and the reason C5 is reachable: any signup
        that supplies a company_name is granted tenant-admin."""
        seen = {}

        async def _capture(db, email, password, company_name):
            seen["company_name"] = company_name
            return _user(role="admin")

        with patch("app.routes.auth.register_user", _capture):
            client_with_db.post(
                "/api/v1/auth/register",
                json={"email": "founder@example.com", "password": "password123", "company_name": "Acme"},
            )
        assert seen["company_name"] == "Acme"

    def test_duplicate_email_returns_409(self, client_with_db):
        with patch("app.routes.auth.register_user", AsyncMock(side_effect=ValueError("Email already registered"))):
            resp = client_with_db.post(
                "/api/v1/auth/register",
                json={"email": "dup@example.com", "password": "password123"},
            )
        assert resp.status_code == 409

    def test_short_password_rejected_by_schema(self, client_with_db):
        resp = client_with_db.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    def test_returns_503_without_database(self, db_mock):
        """Auth is unavailable, not silently open, when no DATABASE_URL."""
        from fastapi.testclient import TestClient

        from app.database import get_db

        app = create_app()

        async def _fake_db():
            yield db_mock

        app.dependency_overrides[get_db] = _fake_db
        with patch("app.routes.auth.is_db_enabled", return_value=False), TestClient(app) as c:
            resp = c.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "password123"})
        app.dependency_overrides.clear()
        assert resp.status_code == 503


# ─────────────────────────────────────────────
# POST /api/v1/auth/login
# ─────────────────────────────────────────────


class TestLogin:
    def test_valid_credentials_return_tokens(self, client_with_db, db_mock):
        db_mock.execute.return_value.scalar_one_or_none.return_value = _user()
        with patch("app.routes.auth.authenticate_user", AsyncMock(return_value=_user())):
            resp = client_with_db.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "password123"},
            )
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_invalid_credentials_return_401(self, client_with_db):
        with patch("app.routes.auth.authenticate_user", AsyncMock(return_value=None)):
            resp = client_with_db.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "wrong"},
            )
        assert resp.status_code == 401

    def test_unknown_email_returns_401(self, client_with_db):
        with patch("app.routes.auth.authenticate_user", AsyncMock(return_value=None)):
            resp = client_with_db.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "password123"},
            )
        assert resp.status_code == 401

    def test_missing_fields_return_422(self, client_with_db):
        assert client_with_db.post("/api/v1/auth/login", json={"email": "user@example.com"}).status_code == 422


# ─────────────────────────────────────────────
# POST /api/v1/auth/refresh
# ─────────────────────────────────────────────


class TestRefresh:
    def test_valid_refresh_token_returns_new_pair(self, client_with_db):
        from app.services.auth import create_refresh_token

        resp = client_with_db.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": create_refresh_token({"sub": _USER_ID})},
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_access_token_is_rejected(self, client_with_db):
        """The client holds both tokens; sending the wrong one must fail."""
        from app.services.auth import create_access_token

        resp = client_with_db.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": create_access_token({"sub": _USER_ID})},
        )
        assert resp.status_code == 401

    def test_garbage_token_rejected(self, client_with_db):
        resp = client_with_db.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
        assert resp.status_code == 401
