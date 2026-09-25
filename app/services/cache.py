"""
Redis caching helpers. All functions fail silently so the app stays up
if Redis is unavailable — cache misses just hit the DB instead.
"""

import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as exc:
            logger.warning("redis unavailable, caching disabled", extra={"error": str(exc)})
    return _redis


async def get_cached(key: str) -> str | None:
    r = get_redis()
    if not r:
        return None
    try:
        return await r.get(key)
    except Exception as exc:
        logger.warning("redis get failed", extra={"key": key, "error": str(exc)})
        return None


async def set_cached(key: str, value: str, ttl: int = 60) -> None:
    r = get_redis()
    if not r:
        return
    try:
        await r.setex(key, ttl, value)
    except Exception as exc:
        logger.warning("redis set failed", extra={"key": key, "error": str(exc)})


async def delete_cached(key: str) -> None:
    r = get_redis()
    if not r:
        return
    try:
        await r.delete(key)
    except Exception as exc:
        logger.warning("redis delete failed", extra={"key": key, "error": str(exc)})
