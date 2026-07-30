"""
Cache service for distance matrices and job results.
Uses Redis when available, falls back to in-process LRU cache.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from typing import Any

import numpy as np
import structlog
from cachetools import LRUCache

logger = structlog.get_logger(__name__)

# In-process LRU (stores up to 20 matrices – each can be 600×600×8 bytes ≈ 2.9 MB)
_lru: LRUCache = LRUCache(maxsize=20)

_redis_client: Any | None = None


def _init_redis(url: str) -> None:
    global _redis_client
    try:
        import redis

        _redis_client = redis.from_url(url, decode_responses=False, socket_connect_timeout=2)
        _redis_client.ping()
        safe_url = url.split("@")[-1] if "@" in url else url
        logger.info("redis_connected", url=safe_url)
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))
        _redis_client = None


def init_cache(redis_url: str | None = None) -> None:
    if redis_url:
        _init_redis(redis_url)


def is_redis_connected() -> bool:
    """Check if Redis client is available and connected."""
    if _redis_client is None:
        return False
    try:
        _redis_client.ping()
        return True
    except Exception:
        return False


def _matrix_key(coords: list[tuple[float, float]], backend: str) -> str:
    raw = json.dumps({"coords": coords, "backend": backend}, sort_keys=True)
    return "matrix:" + hashlib.sha256(raw.encode()).hexdigest()


def get_matrix(coords: list[tuple[float, float]], backend: str) -> tuple | None:
    key = _matrix_key(coords, backend)

    # Redis first
    if _redis_client:
        try:
            data = _redis_client.get(key)
            if data:
                logger.info("cache_hit_redis", key=key[:24])
                decoded = json.loads(data)
                return (
                    np.array(decoded["dist"]),
                    np.array(decoded["dur"]),
                    decoded["source"],
                )
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
            dist_km, dur_s, matrix_source = value
            serialized = json.dumps(
                {
                    "dist": dist_km.tolist(),
                    "dur": dur_s.tolist(),
                    "source": matrix_source,
                }
            )
            _redis_client.setex(key, ttl_seconds, serialized)
            logger.info("cache_set_redis", key=key[:24], ttl=ttl_seconds)
        except Exception as exc:
            logger.warning("redis_set_error", error=str(exc))


# Simple job-result cache (keyed by job_id)
_job_cache: LRUCache = LRUCache(maxsize=200)


def get_job(job_id: str) -> dict | None:
    return _job_cache.get(job_id)


def list_jobs(limit: int = 10) -> list[dict]:
    """Return summaries of the most recent jobs from the in-process cache."""
    jobs = list(_job_cache.keys())[-limit:]
    summaries = []
    for jid in jobs:
        data = _job_cache.get(jid, {})
        summaries.append(
            {
                "job_id": jid,
                "status": data.get("status"),
                "total_locations": data.get("total_locations"),
                "assigned_count": data.get("assigned_count"),
                "unassigned_count": data.get("unassigned_count"),
                "vehicles_used": data.get("vehicles_used"),
                "total_distance_km": data.get("total_distance_km"),
                "solver_time_seconds": data.get("solver_time_seconds"),
            }
        )
    return summaries


def set_job(job_id: str, result: dict, ttl_seconds: int = 7200) -> None:
    _job_cache[job_id] = result
    if _redis_client:
        with suppress(Exception):
            _redis_client.setex(f"job:{job_id}", ttl_seconds, json.dumps(result))


# ── Progress tracking (in-flight solver status) ─────────────
_progress_store: dict[str, dict] = {}


def set_progress(run_id: str, stage: str, pct: float, message: str) -> None:
    _progress_store[run_id] = {"stage": stage, "pct": pct, "message": message}


def get_progress(run_id: str) -> dict | None:
    return _progress_store.get(run_id)


def clear_progress(run_id: str) -> None:
    _progress_store.pop(run_id, None)
