"""
FastAPI dependencies for authentication and authorization.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, is_db_enabled
from app.models.db import ApiKey, User
from app.services.api_keys import authenticate_api_key
from app.services.auth import decode_token

security = HTTPBearer(auto_error=False)


class ApiKeyPrincipal:
    """Authenticated via an API key (B2B integration), scoped to a company."""

    def __init__(self, company_id, api_key: ApiKey):
        self.company_id = company_id
        self.api_key = api_key


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Returns User if DB + valid token present, else None (graceful fallback)."""
    if not is_db_enabled() or credentials is None:
        return None

    payload = decode_token(credentials.credentials, expected_type="access")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active).options(selectinload(User.company))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def require_user(user: User | None = Depends(get_current_user)) -> User:
    """Same as get_current_user but raises 401 if None."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    """Require the user to have admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_current_principal(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | ApiKeyPrincipal | None:
    """Resolve authentication: prefers an X-API-Key header, falls back to JWT bearer."""
    if x_api_key:
        if not is_db_enabled():
            return None
        api_key = await authenticate_api_key(db, x_api_key)
        if api_key is None:
            raise HTTPException(status_code=401, detail="Invalid or expired API key")
        return ApiKeyPrincipal(company_id=api_key.company_id, api_key=api_key)
    return await get_current_user(credentials, db)


async def require_principal(
    principal: User | ApiKeyPrincipal | None = Depends(get_current_principal),
) -> User | ApiKeyPrincipal:
    """Require an authenticated principal (JWT user or API key)."""
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def require_permission(permission: str):
    """Return a dependency requiring the given API-key permission (JWT users always pass)."""

    async def _checker(
        principal: User | ApiKeyPrincipal = Depends(require_principal),
    ) -> User | ApiKeyPrincipal:
        if isinstance(principal, ApiKeyPrincipal):
            permissions = principal.api_key.permissions or []
            if permission not in permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"API key lacks '{permission}' permission",
                )
        return principal

    return _checker
