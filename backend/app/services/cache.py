"""
Cache service for distance matrices and job results.
Uses Redis when available, falls back to in-process LRU cache.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from typing import Any, Optional

import structlog
from cachetools import LRUCache

logger = structlog.get_logger(__name__)

# In-process LRU (stores up to 20 matrices – each can be 600×600×8 bytes ≈ 2.9 MB)
_lru: LRUCache = LRUCache(maxsize=20)

_redis_client: Optional[Any] = None


def _init_redis(url: str) -> None:
    global _redis_client
    try:
        import redis
        _redis_client = redis.from_url(url, decode_responses=False, socket_connect_timeout=2)
        _redis_client.ping()
        logger.info("redis_connected", url=url)
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))
        _redis_client = None


def init_cache(redis_url: Optional[str] = None) -> None:
    if redis_url:
        _init_redis(redis_url)


def _matrix_key(coords: list[tuple[float, float]], backend: str) -> str:
    raw = json.dumps({"coords": coords, "backend": backend}, sort_keys=True)
    return "matrix:" + hashlib.sha256(raw.encode()).hexdigest()


def get_matrix(
    coords: list[tuple[float, float]], backend: str
) -> Optional[tuple]:
    key = _matrix_key(coords, backend)

    # Redis first
    if _redis_client:
        try:
            data = _redis_client.get(key)
            if data:
                logger.info("cache_hit_redis", key=key[:24])
                return pickle.loads(data)
        except Exception as exc:
            logger.warning("redis_get_error", error=str(exc))

    # LRU
    val = _lru.get(key)
    if val is not None:
        logger.info("cache_hit_lru", key=key[:24])
        return val

    return None


def set_matrix(
    coords: list[tuple[float, float]],
    backend: str,
    value: tuple,
    ttl_seconds: int = 3600,
) -> None:
    key = _matrix_key(coords, backend)

    # LRU
    _lru[key] = value

    # Redis
    if _redis_client:
        try:
            _redis_client.setex(key, ttl_seconds, pickle.dumps(value))
            logger.info("cache_set_redis", key=key[:24], ttl=ttl_seconds)
        except Exception as exc:
            logger.warning("redis_set_error", error=str(exc))


# Simple job-result cache (keyed by job_id)
_job_cache: LRUCache = LRUCache(maxsize=200)


def get_job(job_id: str) -> Optional[dict]:
    return _job_cache.get(job_id)


def set_job(job_id: str, result: dict, ttl_seconds: int = 7200) -> None:
    _job_cache[job_id] = result
    if _redis_client:
        try:
            _redis_client.setex(f"job:{job_id}", ttl_seconds, json.dumps(result))
        except Exception:
            pass
