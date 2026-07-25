"""
Async SQLAlchemy database session management.
PostgreSQL is optional — app works without DATABASE_URL.
"""

from __future__ import annotations

from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = structlog.get_logger(__name__)

_engine = None
_session_factory = None


def init_db(database_url: Optional[str]) -> None:
    global _engine, _session_factory
    if not database_url:
        logger.info("database_disabled", reason="DATABASE_URL not set")
        return
    _engine = create_async_engine(database_url, echo=False, pool_size=5, max_overflow=10)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    logger.info("database_connected", url=database_url.split("@")[-1])


def is_db_enabled() -> bool:
    return _session_factory is not None


async def get_db() -> AsyncGenerator[Optional[AsyncSession], None]:
    if _session_factory is None:
        yield None
        return
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
