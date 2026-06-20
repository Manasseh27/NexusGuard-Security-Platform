"""
Dependency Injection Container — thread-safe singleton registry.
Replaces the global-mutable pattern in dependencies.py.
All services are lazily initialized and cached via asyncio.Lock.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar

import structlog

log = structlog.get_logger(__name__)

T = TypeVar("T")


class ServiceContainer:
    """
    Async-safe service container.
    Services are built once on first access and reused for the process lifetime.
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, key: str, factory) -> Any:
        async with self._lock:
            if key not in self._services:
                service = factory()
                self._services[key] = service
                log.info("container.service.created", key=key)
            return self._services[key]

    def get(self, key: str) -> Any | None:
        return self._services.get(key)

    def set(self, key: str, service: Any) -> None:
        self._services[key] = service

    def clear(self) -> None:
        self._services.clear()


# Process-level singleton container
_container = ServiceContainer()


def get_container() -> ServiceContainer:
    return _container
