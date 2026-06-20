"""
Event dispatcher — publishes compliance and drift events to multiple channels.
Decouples event emission from polling logic.
"""

from __future__ import annotations

from typing import Callable, Coroutine

import structlog

from app.domain.compliance.models import DriftEvent, DriftSeverity
from app.services.siem.siem_pipeline import (
    SIEMPipeline,
    NormalizedEvent,
    SIEMEventType,
    SIEMSeverity,
)
from app.infrastructure.messaging.events import (
    get_event_bus,
    ComplianceDriftDetected,
    DeviceUnreachable,
)

log = structlog.get_logger(__name__)


class EventDispatcher:
    """
    Dispatches compliance and drift events to:
    - SIEM platform (Splunk, Sentinel, etc.)
    - Webhook handlers
    - Internal event bus (future)
    """

    def __init__(self, siem_pipeline: SIEMPipeline | None = None) -> None:
        self._siem = siem_pipeline
        self._handlers: list[Callable[[DriftEvent], Coroutine]] = []

    def register_handler(self, handler: Callable[[DriftEvent], Coroutine]) -> None:
        """Register a webhook or custom handler for drift events."""
        self._handlers.append(handler)
        log.info("event_dispatcher.handler.registered")

    async def dispatch_drift_events(self, drifts: list[DriftEvent]) -> None:
        """
        Dispatch multiple drift events to all registered handlers.
        """
        for drift in drifts:
            await self.dispatch_drift(drift)

    async def dispatch_drift(self, drift: DriftEvent) -> None:
        """
        Dispatch a single drift event to SIEM, domain event bus, and handlers.
        """
        log.warning(
            "event.drift.dispatching",
            drift_id=drift.drift_id,
            device_id=drift.device_id,
            severity=drift.severity.value,
        )

        # Publish to internal domain event bus
        domain_event = ComplianceDriftDetected(
            correlation_id=drift.drift_id,
            device_id=drift.device_id,
            device_ip=drift.device_ip,
            framework=drift.framework,
            rule_id=drift.rule_id,
            severity=drift.severity.value,
            score_delta=float(drift.score_delta),
            config_hash_before=drift.config_hash_before,
            config_hash_after=drift.config_hash_after,
        )
        await get_event_bus().publish(domain_event)

        # Emit to SIEM platform
        if self._siem:
            await self._dispatch_to_siem(drift)

        # Call registered handlers (webhooks, email, PagerDuty, etc.)
        for handler in self._handlers:
            try:
                await handler(drift)
            except Exception as exc:
                log.error("event_dispatcher.handler_failed", error=str(exc))

    async def _dispatch_to_siem(self, drift: DriftEvent) -> None:
        """Convert drift event to normalized SIEM event and export."""
        severity_map = {
            DriftSeverity.CRITICAL: SIEMSeverity.CRITICAL,
            DriftSeverity.HIGH: SIEMSeverity.HIGH,
            DriftSeverity.MEDIUM: SIEMSeverity.MEDIUM,
            DriftSeverity.LOW: SIEMSeverity.LOW,
        }

        event = NormalizedEvent(
            event_type=SIEMEventType.DRIFT_DETECTED,
            severity=severity_map[drift.severity],
            device_id=drift.device_id,
            device_ip=drift.device_ip,
            action="compliance_drift_detected",
            outcome="alert",
            rule_id=drift.rule_id,
            framework=drift.framework,
            description=f"Compliance drift on {drift.rule_name}: {drift.previous_result} → {drift.current_result}",
            raw_data={
                "drift_id": drift.drift_id,
                "score_delta": str(drift.score_delta),
                "config_hash_before": drift.config_hash_before,
                "config_hash_after": drift.config_hash_after,
            },
        )

        try:
            await self._siem.emit(event)
            log.info("event.drift.siem_dispatched", drift_id=drift.drift_id)
        except Exception as exc:
            log.error(
                "event.drift.siem_failed",
                drift_id=drift.drift_id,
                error=str(exc),
            )

    async def dispatch_unreachable(
        self,
        device_id: str,
        device_ip: str,
    ) -> None:
        """Dispatch device unreachable event."""
        drift = DriftEvent(
            device_id=device_id,
            device_ip=device_ip,
            framework="platform",
            rule_id="DEVICE-UNREACHABLE",
            rule_name="Device Reachability",
            severity=DriftSeverity.HIGH,
            current_result="unreachable",
            previous_result="reachable",
        )

        # Also publish typed domain event
        await get_event_bus().publish(DeviceUnreachable(
            device_id=device_id,
            device_ip=device_ip,
        ))

        await self.dispatch_drift(drift)
