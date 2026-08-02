"""
API key service: generation, hashing, and authentication for B2B integrations.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import ApiKey

logger = structlog.get_logger(__name__)

API_KEY_PREFIX = "rf_"
PERMISSION_OPTIMIZE = "optimize"
PERMISSION_READ = "read"


def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext_key, display_prefix, sha256_hash)."""
    secret = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}{secret}"
    return full_key, full_key[:12], hash_api_key(full_key)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def create_api_key(
    db: AsyncSession,
    company_id,
    name: str,
    permissions: list[str],
    expires_at: datetime | None,
) -> tuple[ApiKey, str]:
    """Persist a new API key and return (model, plaintext_key). Plaintext is only available here."""
    full_key, prefix, key_hash = generate_api_key()
    key = ApiKey(
        company_id=company_id,
        name=name,
        key_hash=key_hash,
        prefix=prefix,
        permissions=permissions,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    logger.info("api_key_created", company_id=str(company_id), name=name)
    return key, full_key


async def authenticate_api_key(db: AsyncSession, key: str) -> ApiKey | None:
    """Look up a key by its hash. Returns the model when valid, active, and not expired."""
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == hash_api_key(key), ApiKey.is_active))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if api_key.expires_at is not None and api_key.expires_at < datetime.now(UTC):
        return None
    api_key.last_used_at = datetime.now(UTC)
    await db.commit()
    return api_key
