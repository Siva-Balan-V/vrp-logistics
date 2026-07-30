"""
FastAPI dependencies for authentication and authorization.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, is_db_enabled
from app.models.db import User
from app.services.auth import decode_token

security = HTTPBearer(auto_error=False)


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

    result = await db.execute(select(User).where(User.id == user_id, User.is_active))
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
