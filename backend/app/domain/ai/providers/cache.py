"""
AI response caching — Redis-backed LRU cache for identical queries.
"""

from __future__ import annotations

import hashlib
import json

import structlog

from app.domain.ai.providers.models import CopilotOperation, LLMMessage

log = structlog.get_logger(__name__)


class AIResponseCache:
    """Redis-backed LRU cache for AI responses to identical queries."""

    def __init__(self, redis_client=None, ttl: int = 3600) -> None:
        self._redis = redis_client
        self._ttl = ttl

    def _cache_key(self, operation: CopilotOperation, context_hash: str) -> str:
        """Generate cache key for operation and context."""
        return f"ai:cache:{operation.value}:{context_hash}"

    def _hash_context(self, messages: list[LLMMessage]) -> str:
        """Hash message context for cache key."""
        payload = json.dumps(
            [{"role": m.role, "content": m.content} for m in messages],
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    async def get(self, operation: CopilotOperation, messages: list[LLMMessage]) -> str | None:
        """Retrieve cached response if available."""
        if not self._redis:
            return None
        key = self._cache_key(operation, self._hash_context(messages))
        try:
            cached = await self._redis.get(key)
            if cached:
                log.debug("cache.hit", operation=operation.value, key=key)
            return cached
        except Exception as exc:
            log.warning("cache.get_failed", error=str(exc))
            return None

    async def set(self, operation: CopilotOperation, messages: list[LLMMessage], response: str) -> None:
        """Cache a response."""
        if not self._redis:
            return
        key = self._cache_key(operation, self._hash_context(messages))
        try:
            await self._redis.setex(key, self._ttl, response)
            log.debug("cache.set", operation=operation.value, key=key, ttl=self._ttl)
        except Exception as exc:
            log.warning("cache.set_failed", error=str(exc))

    async def invalidate(self, operation: CopilotOperation | None = None) -> None:
        """Invalidate cached responses."""
        if not self._redis:
            return
        try:
            if operation:
                pattern = f"ai:cache:{operation.value}:*"
            else:
                pattern = "ai:cache:*"

            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
                log.info("cache.invalidated", pattern=pattern, count=len(keys))
        except Exception as exc:
            log.warning("cache.invalidation_failed", error=str(exc))
