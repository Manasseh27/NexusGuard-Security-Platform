"""
Compliance history store — persists and retrieves compliance snapshots.
Maintains compliance score timeline for trend analysis and historical tracking.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

from app.domain.compliance.models import ComplianceSnapshot

log = structlog.get_logger(__name__)


class ComplianceHistoryStore:
    """
    In-memory + Redis-backed compliance snapshot history.
    
    Stores point-in-time compliance assessments for trending,
    historical analysis, and audit trail.
    """

    def __init__(self, redis_client: Any | None = None, repository: Any | None = None) -> None:
        """
        Args:
            redis_client: Redis async client for distributed caching.
            repository: Database repository for persistent storage.
        """
        self._redis = redis_client
        self._repo = repository
        self._local_cache: dict[str, list[ComplianceSnapshot]] = {}

    async def save_snapshot(self, snapshot: ComplianceSnapshot) -> None:
        """
        Save a compliance snapshot.
        
        Persists to:
        1. Local in-memory cache (recent 288 snapshots)
        2. Redis (for distributed access)
        3. PostgreSQL (for long-term storage)
        """
        key = f"{snapshot.device_id}:{snapshot.framework}"

        # Local cache (in-memory)
        self._local_cache.setdefault(key, []).append(snapshot)
        # Keep last 288 snapshots (24h at 5-min intervals)
        self._local_cache[key] = self._local_cache[key][-288:]

        # Redis cache
        if self._redis:
            try:
                redis_key = f"compliance:history:{snapshot.device_id}:{snapshot.framework}"
                await self._redis.lpush(
                    redis_key,
                    json.dumps({
                        "snapshot_id": snapshot.snapshot_id,
                        "score": str(snapshot.score),
                        "pass_count": snapshot.pass_count,
                        "fail_count": snapshot.fail_count,
                        "created_at": snapshot.created_at.isoformat(),
                    }),
                )
                # Trim to keep last 288 entries
                await self._redis.ltrim(redis_key, 0, 287)
                log.debug("history.snapshot_cached_redis", device_id=snapshot.device_id)
            except Exception as exc:
                log.warning("history.redis_cache_failed", error=str(exc))

        # PostgreSQL persistent storage
        if self._repo:
            try:
                await self._repo.save(snapshot)
                log.debug("history.snapshot_persisted", device_id=snapshot.device_id)
            except Exception as exc:
                log.error("history.persistence_failed", error=str(exc))

    async def get_history(
        self,
        device_id: str,
        framework: str,
        hours: int = 24,
    ) -> list[ComplianceSnapshot]:
        """
        Retrieve compliance snapshots for a device within a time window.
        """
        key = f"{device_id}:{framework}"
        snapshots = self._local_cache.get(key, [])

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [s for s in snapshots if s.created_at >= cutoff]

    async def get_score_trend(
        self,
        device_id: str,
        framework: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """
        Get compliance score trend data for charting.
        """
        history = await self.get_history(device_id, framework, hours)

        return [
            {
                "timestamp": s.created_at.isoformat(),
                "score": float(s.score),
                "pass_count": s.pass_count,
                "fail_count": s.fail_count,
            }
            for s in history
        ]

    async def get_latest_snapshot(
        self,
        device_id: str,
        framework: str,
    ) -> ComplianceSnapshot | None:
        """Get the most recent snapshot for a device/framework."""
        history = await self.get_history(device_id, framework, hours=8760)  # 1 year
        return history[-1] if history else None

    def clear_local_cache(self, device_id: str | None = None) -> None:
        """Clear local cache, optionally for specific device."""
        if device_id:
            keys_to_delete = [k for k in self._local_cache.keys() if k.startswith(f"{device_id}:")]
            for k in keys_to_delete:
                del self._local_cache[k]
        else:
            self._local_cache.clear()
