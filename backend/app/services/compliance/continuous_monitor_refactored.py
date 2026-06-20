"""
Refactored Continuous Compliance Monitor — main orchestrator.

This version uses modular services for polling, drift detection, event dispatch, and remediation.
All monolithic logic has been extracted into separate, testable modules.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

from app.core.config import settings
from app.domain.compliance.models import (
    DeviceMonitoringState,
    MonitoringState,
    ComplianceSnapshot,
)
from app.domain.compliance.engine.compliance_engine import ComplianceOrchestrator, ComplianceFramework

from app.services.compliance.orchestration.scheduler import PollScheduler
from app.services.compliance.orchestration.polling_orchestrator import PollingOrchestrator
from app.services.compliance.detection.drift_detector import DriftDetector
from app.services.compliance.events.dispatcher import EventDispatcher
from app.services.compliance.remediation.coordinator import RemediationCoordinator
from app.services.compliance.history.store import ComplianceHistoryStore

log = structlog.get_logger(__name__)


class ContinuousComplianceMonitor:
    """
    Refactored flagship continuous compliance monitoring engine.
    
    Orchestrates:
    - Device polling schedule (PollScheduler)
    - Polling execution (PollingOrchestrator)
    - Drift detection (DriftDetector)
    - Event dispatch (EventDispatcher)
    - Auto-remediation (RemediationCoordinator)
    - History tracking (ComplianceHistoryStore)
    """

    def __init__(
        self,
        orchestrator: ComplianceOrchestrator,
        config_fetcher: Any,  # NetworkConfigFetcher
        siem_pipeline: Any | None = None,
        redis_client: Any | None = None,
        device_executor: Any | None = None,
    ) -> None:
        """
        Initialize refactored monitor with modular services.
        """
        # Initialize modular services
        self._scheduler = PollScheduler(check_interval=10)
        self._polling = PollingOrchestrator(
            compliance_orchestrator=orchestrator,
            config_fetcher=config_fetcher,
            on_compliance_check=self._on_compliance_check,
            on_drift=self._on_drift,
        )
        self._drift_detector = DriftDetector()
        self._dispatcher = EventDispatcher(siem_pipeline=siem_pipeline)
        self._remediation = RemediationCoordinator(device_executor=device_executor)
        self._history = ComplianceHistoryStore(redis_client=redis_client)

        # State management
        self._devices: dict[str, DeviceMonitoringState] = {}
        self._running = False
        self._running_event: asyncio.Event | None = None
        self._scheduler_task: asyncio.Task | None = None
        self._poll_task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_DEVICE_CONNECTIONS)

    def register_device(
        self,
        device_id: str,
        device_ip: str,
        device_type: str,
        frameworks: list[ComplianceFramework],
        poll_interval: int | None = None,
    ) -> DeviceMonitoringState:
        """Register a device for continuous monitoring."""
        state = DeviceMonitoringState(
            device_id=device_id,
            device_ip=device_ip,
            device_type=device_type,
            frameworks=frameworks,
            poll_interval=poll_interval or settings.COMPLIANCE_POLLING_INTERVAL_SECONDS,
        )
        self._devices[device_id] = state

        # Schedule via asyncio only if event loop is running
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._scheduler.register(device_id, state.next_poll_at))
        except RuntimeError:
            pass  # Not in async context — scheduler will pick up on next loop tick

        log.info(
            "monitor.device_registered",
            device_id=device_id,
            frameworks=[f.value for f in frameworks],
        )
        return state

    def deregister_device(self, device_id: str) -> None:
        """Remove device from monitoring."""
        self._devices.pop(device_id, None)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._scheduler.deregister(device_id))
        except RuntimeError:
            pass
        log.info("monitor.device_deregistered", device_id=device_id)

    async def start(self) -> None:
        """Start the monitoring engine."""
        if not settings.ENABLE_CONTINUOUS_MONITORING:
            log.info("monitor.disabled_by_config")
            return

        self._running = True
        self._running_event = asyncio.Event()
        self._running_event.set()

        self._scheduler_task = asyncio.create_task(
            self._scheduler.run_scheduler_loop(
                on_due=self._poll_due_devices,
                running_flag=self._running_event,
            ),
            name="compliance-scheduler",
        )

        log.info("monitor.started", device_count=len(self._devices))

    async def stop(self) -> None:
        """Stop the monitoring engine."""
        self._running = False
        if hasattr(self, "_running_event"):
            self._running_event.clear()

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        log.info("monitor.stopped")

    async def _poll_due_devices(self, device_ids: list[str]) -> None:
        """Poll devices that are due for polling."""
        tasks = [
            asyncio.create_task(self._poll_device(device_id))
            for device_id in device_ids
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _poll_device(self, device_id: str) -> None:
        """Poll a single device with concurrency limiting."""
        state = self._devices.get(device_id)
        if not state:
            return

        async with self._semaphore:
            try:
                log.debug("monitor.polling_device", device_id=device_id)

                # Update next poll time
                state.next_poll_at = datetime.now(timezone.utc) + timedelta(
                    seconds=state.poll_interval
                )
                state.last_polled = datetime.now(timezone.utc)

                # Poll device using PollingOrchestrator
                result = await self._polling.poll_device(state)

                if result["status"] == "unreachable":
                    state.consecutive_failures += 1
                    state.monitoring_state = MonitoringState.UNREACHABLE

                    if state.consecutive_failures == 3:
                        # Alert after 3 consecutive failures
                        await self._dispatcher.dispatch_unreachable(
                            state.device_id,
                            state.device_ip,
                        )

                # Reschedule device
                await self._scheduler.reschedule(device_id, state.next_poll_at)

            except Exception as exc:
                log.error("monitor.poll_device_error", device_id=device_id, error=str(exc))

    async def _on_compliance_check(
        self,
        state: DeviceMonitoringState,
        snapshot: ComplianceSnapshot,
    ) -> None:
        """Callback when compliance check completes."""
        # Save snapshot to history
        await self._history.save_snapshot(snapshot)

    async def _on_drift(
        self,
        state: DeviceMonitoringState,
        report: Any,  # ComplianceReport
        old_score: Any,
        new_score: Any,
        score_delta: Any,
        config_hash: str,
    ) -> None:
        """Callback when drift is detected."""
        # Detect drift events
        drifts = self._drift_detector.detect_drift(
            state,
            report,
            old_score,
            new_score,
            score_delta,
            config_hash,
        )

        # Dispatch drift events
        await self._dispatcher.dispatch_drift_events(drifts)

        # Trigger remediation for high-severity drifts
        if settings.ENABLE_AUTO_REMEDIATION and self._remediation._executor:
            for drift in drifts:
                if drift.severity.value in ("critical", "high"):
                    asyncio.create_task(
                        self._remediation.execute_remediation(
                            device_id=state.device_id,
                            device_ip=state.device_ip,
                            commands=getattr(report.results[0], "remediation_steps", []),
                            drift_event=drift,
                        )
                    )

    # ── Public API (unchanged for backward compatibility) ──────────────────────

    def get_device_state(self, device_id: str) -> DeviceMonitoringState | None:
        """Get device monitoring state."""
        return self._devices.get(device_id)

    def get_all_states(self) -> list[DeviceMonitoringState]:
        """Get all device states."""
        return list(self._devices.values())

    async def force_poll(self, device_id: str) -> ComplianceSnapshot | None:
        """Force immediate poll of a device."""
        state = self._devices.get(device_id)
        if not state:
            return None

        await self._poll_device(device_id)

        # Return latest snapshot
        history = await self._history.get_history(
            device_id, state.frameworks[0].value if state.frameworks else "cis", hours=1
        )
        return history[-1] if history else None

    async def get_compliance_trend(
        self, device_id: str, framework: str = "cis", hours: int = 24
    ) -> list[dict[str, Any]]:
        """Get compliance score trend."""
        return await self._history.get_score_trend(device_id, framework, hours)

    def get_fleet_summary(self) -> dict[str, Any]:
        """Get fleet-wide compliance summary."""
        states = self.get_all_states()
        total = len(states)

        if total == 0:
            return {"total_devices": 0}

        healthy = sum(1 for s in states if s.monitoring_state == MonitoringState.HEALTHY)
        drifting = sum(1 for s in states if s.monitoring_state == MonitoringState.DRIFTING)
        unreachable = sum(1 for s in states if s.monitoring_state == MonitoringState.UNREACHABLE)
        degraded = total - healthy - drifting - unreachable
        avg_score = sum(float(s.current_score) for s in states) / total if states else 0

        return {
            "total_devices": total,
            "healthy": healthy,
            "drifting": drifting,
            "unreachable": unreachable,
            "degraded": degraded,
            "average_compliance_score": round(avg_score, 2),
            "fleet_health_pct": round(healthy / total * 100, 1) if total else 0,
            "active_drift_events": sum(len(s.active_drift_events) for s in states),
        }
