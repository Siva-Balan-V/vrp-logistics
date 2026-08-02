from __future__ import annotations

import smtplib
import uuid
from abc import ABC, abstractmethod
from email.mime.text import MIMEText

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.db import Driver, NotificationConfig, NotificationLog

logger = structlog.get_logger(__name__)

TRIGGER_LABELS = {
    "out_for_delivery": "Out for Delivery",
    "arrived": "Delivered",
    "delayed": "Delayed",
}


class NotificationProvider(ABC):
    @abstractmethod
    async def send(self, recipient: str, message: str, config: NotificationConfig | None = None) -> bool: ...


class TwilioSMSProvider(NotificationProvider):
    async def send(self, recipient: str, message: str, config: NotificationConfig | None = None) -> bool:
        settings = get_settings()
        sid = (config.twilio_account_sid or settings.TWILIO_ACCOUNT_SID) if config else settings.TWILIO_ACCOUNT_SID
        token = (config.twilio_auth_token or settings.TWILIO_AUTH_TOKEN) if config else settings.TWILIO_AUTH_TOKEN
        from_ = (config.twilio_from_number or settings.TWILIO_FROM_NUMBER) if config else settings.TWILIO_FROM_NUMBER
        if not sid or not token or not from_:
            logger.warning("twilio_not_configured", recipient=recipient)
            return False
        try:
            from twilio.rest import Client

            client = Client(sid, token)
            client.messages.create(body=message, from_=from_, to=recipient)
            logger.info("sms_sent", recipient=recipient)
            return True
        except Exception as e:
            logger.error("sms_failed", recipient=recipient, error=str(e))
            return False


class LogOnlySMSProvider(NotificationProvider):
    async def send(self, recipient: str, message: str, _config: NotificationConfig | None = None) -> bool:
        logger.info("sms_log_only", recipient=recipient, message=message)
        return True


class SMTPEmailProvider(NotificationProvider):
    async def send(self, recipient: str, message: str, config: NotificationConfig | None = None) -> bool:
        settings = get_settings()
        host = (config.smtp_host or settings.SMTP_HOST) if config else settings.SMTP_HOST
        port = (config.smtp_port or settings.SMTP_PORT) if config else settings.SMTP_PORT
        user = (config.smtp_user or settings.SMTP_USER) if config else settings.SMTP_USER
        pw = (config.smtp_password or settings.SMTP_PASSWORD) if config else settings.SMTP_PASSWORD
        from_ = (config.smtp_from_email or settings.SMTP_FROM_EMAIL) if config else settings.SMTP_FROM_EMAIL
        if not host or not user or not pw or not from_:
            logger.warning("smtp_not_configured", recipient=recipient)
            return False
        try:
            msg = MIMEText(message, _charset="utf-8")
            msg["Subject"] = "RouteForge Delivery Notification"
            msg["From"] = from_
            msg["To"] = recipient
            with smtplib.SMTP(host, port) as s:
                s.starttls()
                s.login(user, pw)
                s.send_message(msg)
            logger.info("email_sent", recipient=recipient)
            return True
        except Exception as e:
            logger.error("email_failed", recipient=recipient, error=str(e))
            return False


class LogOnlyEmailProvider(NotificationProvider):
    async def send(self, recipient: str, message: str, _config: NotificationConfig | None = None) -> bool:
        logger.info("email_log_only", recipient=recipient, message=message)
        return True


def _get_sms_provider() -> NotificationProvider:
    settings = get_settings()
    if settings.TWILIO_ACCOUNT_SID:
        return TwilioSMSProvider()
    return LogOnlySMSProvider()


def _get_email_provider() -> NotificationProvider:
    settings = get_settings()
    if settings.SMTP_HOST:
        return SMTPEmailProvider()
    return LogOnlyEmailProvider()


async def send_notification(
    db: AsyncSession,
    company_id: uuid.UUID,
    driver_id: uuid.UUID,
    trigger: str,
    customer_phone: str | None = None,
    customer_email: str | None = None,
) -> list[dict]:
    result = await db.execute(select(NotificationConfig).where(NotificationConfig.company_id == company_id))
    ncfg = result.scalar_one_or_none()
    if not ncfg:
        logger.info("no_notification_config", company_id=str(company_id))
        return []

    if trigger not in (ncfg.triggers or []):
        logger.info("trigger_not_enabled", trigger=trigger)
        return []

    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    driver_name = driver.name if driver else "Unknown"

    label = TRIGGER_LABELS.get(trigger, trigger)
    message = f"RouteForge: {label} - Driver {driver_name} is on the way."

    sent: list[dict] = []

    if ncfg.sms_enabled and customer_phone:
        sms = _get_sms_provider()
        ok = await sms.send(customer_phone, message, ncfg)
        log = NotificationLog(
            company_id=company_id,
            driver_id=driver_id,
            channel="sms",
            recipient=customer_phone,
            trigger=trigger,
            message=message,
            status="sent" if ok else "failed",
            error=None if ok else "provider_error",
        )
        db.add(log)
        sent.append({"channel": "sms", "recipient": customer_phone, "status": "sent" if ok else "failed"})

    if ncfg.email_enabled and customer_email:
        email = _get_email_provider()
        ok = await email.send(customer_email, message, ncfg)
        log = NotificationLog(
            company_id=company_id,
            driver_id=driver_id,
            channel="email",
            recipient=customer_email,
            trigger=trigger,
            message=message,
            status="sent" if ok else "failed",
            error=None if ok else "provider_error",
        )
        db.add(log)
        sent.append({"channel": "email", "recipient": customer_email, "status": "sent" if ok else "failed"})

    await db.flush()
    return sent
