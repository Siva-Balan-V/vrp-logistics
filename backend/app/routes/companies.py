"""
Company management routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user
from app.models.db import Company, User

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.get("/me")
async def get_my_company(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    return {"id": str(company.id), "name": company.name, "plan": company.plan}


@router.get("/me/members")
async def list_members(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.company_id == user.company_id))
    return [{"id": str(u.id), "email": u.email, "role": u.role} for u in result.scalars().all()]
