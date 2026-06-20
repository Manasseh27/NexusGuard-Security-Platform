"""
Device polling orchestrator — coordinates polling, compliance checking, and drift detection.
Extracts the core polling logic from ContinuousComplianceMonitor.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID, uuid4

import structlog

from app.core.config import settings
from app.core.metrics import COMPLIANCE_SCORE
from app.domain.compliance.models import (
    DeviceMonitoringState,
    ComplianceSnapshot,
    MonitoringState,
)
from app.domain.compliance.engine.compliance_engine import ComplianceOrchestrator

log = structlog.get_logger(__name__)


class PollingOrchestrator:
    """
    Orchestrates the polling flow:
    1. Fetch device config
    2. Hash config to detect changes
    3. Run compliance check if changed
    4. Record snapshot
    5. Emit drift events
    """

    def __init__(
        self,
        compliance_orchestrator: ComplianceOrchestrator,
        config_fetcher: Any,  # NetworkConfigFetcher
        on_compliance_check: Callable[[DeviceMonitoringState, Any], Any] | None = None,
        on_drift: Callable[[DeviceMonitoringState, Any], Any] | None = None,
    ) -> None:
        self._orchestrator = compliance_orchestrator
        self._config_fetcher = config_fetcher
        self._on_compliance_check = on_compliance_check
        self._on_drift = on_drift

    async def poll_device(
        self,
        state: DeviceMonitoringState,
    ) -> dict[str, Any]:
        """
        Poll a single device:
        - Fetch config
        - Check compliance
        - Detect drift
        - Record history
        
        Returns status dict.
        """
        device_id = state.device_id
        log.debug("polling.device.starting", device_id=device_id)

        try:
            # Fetch device configuration
            device_config = await self._fetch_config(state)
            if device_config is None:
                return {"status": "unreachable", "device_id": device_id}

            state.consecutive_failures = 0
            state.last_successful = datetime.now(timezone.utc)

            # Hash config and detect changes
            config_hash = self._hash_config(device_config)
            config_changed = config_hash != state.current_config_hash

            # Run compliance check if config changed or no baseline
            if config_changed or state.baseline_score is None:
                await self._run_compliance_check(state, device_config, config_hash, config_changed)
            else:
                log.debug("polling.config_unchanged", device_id=device_id)

            return {"status": "success", "device_id": device_id}

        except Exception as exc:
            log.error("polling.device_error", device_id=device_id, error=str(exc))
            state.consecutive_failures += 1
            return {"status": "failed", "device_id": device_id, "error": str(exc)}

    async def _fetch_config(self, state: DeviceMonitoringState) -> dict[str, Any] | None:
        """Fetch device configuration via SSH/NETCONF."""
        if self._config_fetcher:
            try:
                return await asyncio.wait_for(
                    self._config_fetcher.fetch(state.device_ip, state.device_type),
                    timeout=settings.DEVICE_SSH_TIMEOUT,
                )
            except Exception as exc:
                log.warning("polling.config_fetch_failed", device_id=state.device_id, error=str(exc))
                return None
        log.warning("polling.config_fetch_unavailable", device_id=state.device_id, device_ip=state.device_ip)
        return None

    def _hash_config(self, config: dict[str, Any]) -> str:
        """Hash config dict to detect changes."""
        import hashlib
        import json
        canonical = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def _run_compliance_check(
        self,
        state: DeviceMonitoringState,
        device_config: dict[str, Any],
        config_hash: str,
        config_changed: bool,
    ) -> None:
        """Run compliance evaluation and process results."""
        device_metadata = {
            "device_id": state.device_id,
            "device_ip": state.device_ip,
            "device_type": state.device_type,
        }

        # Evaluate compliance
        report = await self._orchestrator.evaluate_device(
            device_id=UUID(state.device_id) if len(state.device_id) == 36 else uuid4(),
            device_config=device_config,
            device_metadata=device_metadata,
            frameworks=state.frameworks,
            previous_score=state.current_score if state.current_score else None,
        )

        new_score = report.overall_score
        old_score = state.current_score

        # Record snapshot
        snapshot = ComplianceSnapshot(
            device_id=state.device_id,
            framework=report.framework.value,
            score=new_score,
            config_hash=config_hash,
            pass_count=report.pass_count,
            fail_count=report.fail_count,
            report_data={
                "overall_score": float(new_score),
                "critical_failures": len(report.critical_failures),
                "report_id": str(report.report_id),
            },
        )

        # Emit compliance check event
        if self._on_compliance_check:
            await self._on_compliance_check(state, snapshot)

        # Update metrics
        COMPLIANCE_SCORE.labels(
            framework=report.framework.value,
            tenant_id="default",
        ).set(float(new_score))

        # Detect and emit drift
        if config_changed and old_score > 0:
            score_delta = new_score - old_score
            relative_change = abs(float(score_delta)) / float(old_score) if old_score else 0

            if relative_change >= settings.COMPLIANCE_DRIFT_ALERT_THRESHOLD:
                if self._on_drift:
                    await self._on_drift(state, report, old_score, new_score, score_delta, config_hash)

        # Update device state
        state.current_config_hash = config_hash
        state.current_score = new_score

        if state.baseline_score is None:
            state.baseline_score = new_score
            log.info("polling.baseline_set", device_id=state.device_id, score=float(new_score))

        state.monitoring_state = (
            MonitoringState.DRIFTING
            if state.active_drift_events
            else MonitoringState.HEALTHY
        )
