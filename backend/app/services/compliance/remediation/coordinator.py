"""
Remediation coordinator — manages automated remediation workflows with rollback support.
Triggers and coordinates remediation for compliance drift events.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import settings
from app.domain.compliance.models import DriftEvent, DriftSeverity

log = structlog.get_logger(__name__)


class RemediationCoordinator:
    """
    Manages automated remediation workflows:
    - Executes remediation commands on devices
    - Saves rollback points
    - Handles rollback on failure
    - Only activates if ENABLE_AUTO_REMEDIATION=true
    """

    def __init__(self, device_executor: Any | None = None) -> None:
        """
        Args:
            device_executor: NetworkDeviceExecutor for command execution.
        """
        self._executor = device_executor
        self._rollback_configs: dict[str, str] = {}  # device_id → last good config

    async def save_rollback_point(self, device_id: str, config: str) -> None:
        """Save device config for rollback in case of failure."""
        self._rollback_configs[device_id] = config
        log.info("remediation.rollback_point.saved", device_id=device_id)

    async def execute_remediation(
        self,
        device_id: str,
        device_ip: str,
        commands: list[str],
        drift_event: DriftEvent,
    ) -> dict[str, Any]:
        """
        Execute remediation commands on a device.
        
        Returns status dict with execution results.
        """
        # Check if auto-remediation is enabled
        if not settings.ENABLE_AUTO_REMEDIATION:
            log.info("remediation.skipped_disabled", device_id=device_id)
            return {"status": "skipped", "reason": "auto_remediation_disabled"}

        # Don't auto-remediate low-severity drifts
        if drift_event.severity == DriftSeverity.LOW:
            log.info("remediation.skipped_low_severity", device_id=device_id, drift_id=drift_event.drift_id)
            return {"status": "skipped", "reason": "low_severity"}

        log.info(
            "remediation.executing",
            device_id=device_id,
            commands_count=len(commands),
            drift_id=drift_event.drift_id,
            severity=drift_event.severity.value,
        )

        if not self._executor:
            log.warning("remediation.no_executor", device_id=device_id)
            return {"status": "skipped", "reason": "no_executor"}

        try:
            result = await self._executor.execute_commands(
                device_ip=device_ip,
                commands=commands,
                timeout=settings.DEVICE_COMMAND_TIMEOUT,
            )

            log.info(
                "remediation.success",
                device_id=device_id,
                drift_id=drift_event.drift_id,
            )

            return {
                "status": "success",
                "result": result,
                "drift_id": drift_event.drift_id,
            }

        except Exception as exc:
            log.error(
                "remediation.execution_failed",
                device_id=device_id,
                error=str(exc),
            )

            # Attempt rollback on failure
            rolled_back = await self._rollback(device_id, device_ip)

            return {
                "status": "failed",
                "error": str(exc),
                "rolled_back": rolled_back,
                "drift_id": drift_event.drift_id,
            }

    async def _rollback(self, device_id: str, device_ip: str) -> bool:
        """
        Rollback device config to last known good state.
        
        Returns True if rollback succeeded, False otherwise.
        """
        rollback_config = self._rollback_configs.get(device_id)

        if not rollback_config:
            log.error("remediation.rollback_no_config", device_id=device_id)
            return False

        if not self._executor:
            log.error("remediation.rollback_no_executor", device_id=device_id)
            return False

        log.warning("remediation.rollback_initiated", device_id=device_id)

        try:
            await self._executor.apply_config(device_ip=device_ip, config=rollback_config)
            log.info("remediation.rollback_success", device_id=device_id)
            return True

        except Exception as exc:
            log.critical(
                "remediation.rollback_FAILED",
                device_id=device_id,
                error=str(exc),
            )
            return False
