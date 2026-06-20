"""
Domain events — typed event definitions and async event bus.

Implements:
- Typed domain event classes
- Async event bus with fan-out dispatch
- Retry handling with exponential backoff
- Dead-letter queue (DLQ) for failed events
- Structured logging for all event lifecycle stages
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar
from uuid import uuid4

import structlog

log = structlog.get_logger(__name__)

EventHandler = Callable[[Any], Coroutine[Any, Any, None]]
E = TypeVar("E", bound="DomainEvent")


# ── Event base ─────────────────────────────────────────────────────────────────

@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None
    retry_count: int = 0


# ── Typed domain events ────────────────────────────────────────────────────────

@dataclass
class ComplianceDriftDetected(DomainEvent):
    device_id: str = ""
    device_ip: str = ""
    framework: str = ""
    rule_id: str = ""
    severity: str = "medium"
    score_delta: float = 0.0
    config_hash_before: str = ""
    config_hash_after: str = ""


@dataclass
class ComplianceEvaluationCompleted(DomainEvent):
    device_id: str = ""
    framework: str = ""
    score: float = 0.0
    pass_count: int = 0
    fail_count: int = 0
    critical_failures: int = 0


@dataclass
class DeviceUnreachable(DomainEvent):
    device_id: str = ""
    device_ip: str = ""
    consecutive_failures: int = 0


@dataclass
class RemediationTriggered(DomainEvent):
    device_id: str = ""
    drift_id: str = ""
    commands: list[str] = field(default_factory=list)
    severity: str = ""


@dataclass
class RemediationCompleted(DomainEvent):
    device_id: str = ""
    drift_id: str = ""
    status: str = ""  # success | failed | rolled_back
    error: str | None = None


@dataclass
class SIEMExportFailed(DomainEvent):
    platform: str = ""
    event_id: str = ""
    error: str = ""
    batch_size: int = 0


@dataclass
class AuditEventRecorded(DomainEvent):
    user_id: str = ""
    action: str = ""
    resource: str = ""
    outcome: str = ""


# ── Dead-letter queue ──────────────────────────────────────────────────────────

@dataclass
class DeadLetterEntry:
    event: DomainEvent
    handler_name: str
    error: str
    failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0


class DeadLetterQueue:
    """
    In-memory DLQ for failed event deliveries.
    Production: back with Redis LPUSH / PostgreSQL for persistence.
    """

    MAX_SIZE = 10_000

    def __init__(self) -> None:
        self._entries: list[DeadLetterEntry] = []

    def push(self, entry: DeadLetterEntry) -> None:
        if len(self._entries) >= self.MAX_SIZE:
            self._entries.pop(0)  # Evict oldest
        self._entries.append(entry)
        log.error(
            "dlq.event_dead_lettered",
            event_type=type(entry.event).__name__,
            handler=entry.handler_name,
            error=entry.error,
            attempts=entry.attempts,
        )

    def drain(self) -> list[DeadLetterEntry]:
        entries = list(self._entries)
        self._entries.clear()
        return entries

    def size(self) -> int:
        return len(self._entries)

    def get_recent(self, limit: int = 50) -> list[DeadLetterEntry]:
        return self._entries[-limit:]


# ── Event bus ─────────────────────────────────────────────────────────────────

class EventBus:
    """
    Async domain event bus with:
    - Fan-out to multiple handlers per event type
    - Per-handler retry with exponential backoff
    - Dead-letter queue for exhausted retries
    - Structured logging for observability
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 0.5  # seconds

    def __init__(self) -> None:
        self._handlers: dict[type, list[tuple[str, EventHandler]]] = {}
        self._dlq = DeadLetterQueue()
        self._published_count = 0
        self._failed_count = 0

    def subscribe(self, event_type: type[E], handler: EventHandler, name: str | None = None) -> None:
        """Register a handler for an event type."""
        handler_name = name or getattr(handler, "__name__", repr(handler))
        self._handlers.setdefault(event_type, []).append((handler_name, handler))
        log.debug("event_bus.handler_registered", event_type=event_type.__name__, handler=handler_name)

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all registered handlers."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            log.debug("event_bus.no_handlers", event_type=event_type.__name__)
            return

        self._published_count += 1
        log.debug(
            "event_bus.publishing",
            event_type=event_type.__name__,
            event_id=event.event_id,
            handler_count=len(handlers),
        )

        tasks = [
            asyncio.create_task(self._dispatch_with_retry(event, name, handler))
            for name, handler in handlers
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _dispatch_with_retry(
        self, event: DomainEvent, handler_name: str, handler: EventHandler
    ) -> None:
        """Dispatch to a single handler with retry + DLQ fallback."""
        last_exc: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                await handler(event)
                return
            except Exception as exc:
                last_exc = exc
                delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                log.warning(
                    "event_bus.handler_retry",
                    event_type=type(event).__name__,
                    handler=handler_name,
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(exc),
                )
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(delay)

        # All retries exhausted — dead-letter
        self._failed_count += 1
        self._dlq.push(DeadLetterEntry(
            event=event,
            handler_name=handler_name,
            error=str(last_exc),
            attempts=self.MAX_RETRIES,
        ))

    def get_stats(self) -> dict[str, Any]:
        return {
            "published": self._published_count,
            "failed": self._failed_count,
            "dlq_size": self._dlq.size(),
            "registered_event_types": [t.__name__ for t in self._handlers],
        }

    @property
    def dlq(self) -> DeadLetterQueue:
        return self._dlq


# ── Singleton event bus ────────────────────────────────────────────────────────

_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
