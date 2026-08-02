from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user
from app.models.db import NotificationConfig, NotificationLog, User
from app.models.schemas import (
    NotificationConfigResponse,
    NotificationConfigUpdate,
    NotificationLogResponse,
    TriggerNotificationRequest,
)
from app.services.notifications import send_notification

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/config", response_model=NotificationConfigResponse | None)
async def get_notification_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    result = await db.execute(select(NotificationConfig).where(NotificationConfig.company_id == user.company_id))
    cfg = result.scalar_one_or_none()
    return cfg


@router.put("/config", response_model=NotificationConfigResponse)
async def upsert_notification_config(
    body: NotificationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    result = await db.execute(select(NotificationConfig).where(NotificationConfig.company_id == user.company_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        cfg = NotificationConfig(company_id=user.company_id)
        db.add(cfg)

    updates = body.model_dump(exclude_none=True)
    for key, val in updates.items():
        setattr(cfg, key, val)
    await db.flush()
    await db.refresh(cfg)
    logger.info("notification_config_updated", company_id=str(user.company_id))
    return cfg


@router.post("/trigger")
async def trigger_notification(
    body: TriggerNotificationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    sent = await send_notification(
        db,
        company_id=user.company_id,
        driver_id=uuid.UUID(body.driver_id),
        trigger=body.trigger,
        customer_phone=body.customer_phone,
        customer_email=body.customer_email,
    )
    return {"sent": sent}


@router.get("/logs", response_model=list[NotificationLogResponse])
async def list_notification_logs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    limit: int = 50,
):
    result = await db.execute(
        select(NotificationLog)
        .where(NotificationLog.company_id == user.company_id)
        .order_by(desc(NotificationLog.created_at))
        .limit(limit)
    )
    return result.scalars().all()
