"""
Authentication routes: register, login, refresh, me.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, is_db_enabled
from app.dependencies import require_user
from app.models.db import User
from app.models.schemas import TokenRefresh, TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    register_user,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    if not is_db_enabled():
        raise HTTPException(503, "Auth requires database. Set DATABASE_URL.")
    try:
        user = await register_user(db, body.email, body.password, body.company_name)
    except ValueError as e:
        raise HTTPException(409, str(e))

    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    if not is_db_enabled():
        raise HTTPException(503, "Auth requires database. Set DATABASE_URL.")
    user = await authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")

    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    if not is_db_enabled():
        raise HTTPException(503, "Auth requires database. Set DATABASE_URL.")
    payload = decode_token(body.refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(401, "Invalid refresh token")
    user_id = payload.get("sub")
    access = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})
    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(require_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        company_id=str(user.company_id),
        company_name=user.company.name if user.company else "",
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )
