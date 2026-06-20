"""
Redis client with async connection pooling.
Used for: session cache, rate limiting, AI response cache, pub/sub, compliance history.
"""

from __future__ import annotations

import structlog
from redis.asyncio import Redis, ConnectionPool
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import RedisError

from app.core.config import settings

log = structlog.get_logger(__name__)

_redis_client: Redis | None = None
_pool: ConnectionPool | None = None


async def init_redis() -> None:
    global _redis_client, _pool
    _pool = ConnectionPool.from_url(
        settings.redis.url,
        max_connections=settings.redis.POOL_SIZE,
        socket_timeout=settings.redis.TIMEOUT,
        socket_connect_timeout=settings.redis.TIMEOUT,
        retry=Retry(ExponentialBackoff(), 3),
        retry_on_error=[RedisError],
        decode_responses=True,
    )
    _redis_client = Redis(connection_pool=_pool)
    await _redis_client.ping()
    log.info("redis.initialized", host=settings.redis.HOST)


async def close_redis() -> None:
    global _redis_client, _pool
    if _redis_client:
        await _redis_client.aclose()
    if _pool:
        await _pool.aclose()
    log.info("redis.closed")


def get_redis() -> Redis | None:
    return _redis_client


async def check_redis_health() -> bool:
    if not _redis_client:
        return False
    try:
        return await _redis_client.ping()
    except Exception as exc:
        log.error("redis.health_check.failed", error=str(exc))
        return False


async def token_revoked(token_id: str) -> bool:
    if not _redis_client:
        return False
    return bool(await _redis_client.exists(f"jwt:revoked:{token_id}"))


async def revoke_jwt(token_id: str, ttl_seconds: int, token_type: str = "token") -> None:
    if not _redis_client or ttl_seconds <= 0:
        return
    await _redis_client.setex(f"jwt:revoked:{token_id}", ttl_seconds, token_type)
