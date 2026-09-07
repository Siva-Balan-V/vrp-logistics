"""
Async SQLAlchemy database session management.
PostgreSQL is optional — app works without DATABASE_URL.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = structlog.get_logger(__name__)

_engine = None
_session_factory = None


def init_db(database_url: str | None) -> None:
    global _engine, _session_factory
    if not database_url:
        logger.info("database_disabled", reason="DATABASE_URL not set")
        return
    _engine = create_async_engine(database_url, echo=False, pool_size=5, max_overflow=10)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def wait_for_db(database_url: str | None, retries: int = 10, delay: float = 2.0) -> bool:
    if not database_url:
        return False
    engine = create_async_engine(database_url, echo=False)
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            logger.info("database_connected", url=database_url.split("@")[-1])
            return True
        except Exception as exc:
            logger.warning("db_connect_retry", attempt=attempt, max_retries=retries, error=str(exc))
            await asyncio.sleep(delay)
    await engine.dispose()
    logger.error("database_unreachable", url=database_url.split("@")[-1])
    return False


def is_db_enabled() -> bool:
    return _session_factory is not None


def run_migrations(database_url: str) -> None:
    """Run alembic upgrade head synchronously (called once at startup)."""
    from alembic.config import Config

    from alembic import command

    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("alembic_ini_missing", path=str(alembic_ini))
        return
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", database_url)
    try:
        command.upgrade(cfg, "head")
        logger.info("migrations_applied")
    except Exception:
        logger.exception("migrations_failed")


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
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
