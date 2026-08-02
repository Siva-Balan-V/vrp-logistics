"""
API key management routes (B2B integrations).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, is_db_enabled
from app.dependencies import require_admin
from app.models.db import ApiKey, User
from app.models.schemas import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.services.api_keys import create_api_key

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


def _to_response(key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=str(key.id),
        name=key.name,
        prefix=key.prefix,
        permissions=key.permissions or [],
        is_active=key.is_active,
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
        created_at=key.created_at.isoformat() if key.created_at else None,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not is_db_enabled():
        raise HTTPException(503, "API keys require a database. Set DATABASE_URL.")
    result = await db.execute(
        select(ApiKey).where(ApiKey.company_id == user.company_id).order_by(ApiKey.created_at.desc())
    )
    return [_to_response(k) for k in result.scalars().all()]


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_key(
    body: ApiKeyCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not is_db_enabled():
        raise HTTPException(503, "API keys require a database. Set DATABASE_URL.")
    key, full_key = await create_api_key(db, user.company_id, body.name, body.permissions, body.expires_at)
    resp = _to_response(key).model_dump()
    resp["key"] = full_key
    return ApiKeyCreatedResponse(**resp)


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not is_db_enabled():
        raise HTTPException(503, "API keys require a database. Set DATABASE_URL.")
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.company_id == user.company_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "API key not found")
    key.is_active = False
    await db.commit()
    return {"status": "revoked", "id": str(key.id)}
