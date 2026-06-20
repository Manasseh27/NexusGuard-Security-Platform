"""
Drift detector — identifies and analyzes compliance drift events.
Separates drift detection logic from polling orchestration.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from app.core.metrics import COMPLIANCE_DRIFT_EVENTS
from app.domain.compliance.models import (
    DeviceMonitoringState,
    DriftEvent,
    DriftSeverity,
)
from app.domain.compliance.engine.compliance_engine import (
    ComplianceReport,
    RuleSeverity,
)

log = structlog.get_logger(__name__)


class DriftDetector:
    """
    Analyzes compliance changes and creates drift events.
    Determines severity levels and identifies which rules changed.
    """

    @staticmethod
    def detect_drift(
        state: DeviceMonitoringState,
        report: ComplianceReport,
        old_score: Decimal,
        new_score: Decimal,
        score_delta: Decimal,
        new_config_hash: str,
    ) -> list[DriftEvent]:
        """
        Detect drift by analyzing score changes and failed rules.
        
        Returns list of DriftEvent objects representing the drift.
        """
        drifts: list[DriftEvent] = []

        # Determine overall severity based on score change
        severity = DriftDetector._calculate_severity(report, score_delta)

        log.warning(
            "drift.detected",
            device_id=state.device_id,
            severity=severity.value,
            score_delta=float(score_delta),
            old_score=float(old_score),
            new_score=float(new_score),
        )

        COMPLIANCE_DRIFT_EVENTS.labels(
            severity=severity.value,
            framework=report.framework.value,
        ).inc()

        # Create drift events for each new failure
        for result in report.results:
            if result.failed:
                drift = DriftEvent(
                    device_id=state.device_id,
                    device_ip=state.device_ip,
                    framework=report.framework.value,
                    rule_id=result.rule_id,
                    rule_name=result.rule_name,
                    severity=DriftDetector._map_severity(result.severity, severity),
                    previous_result="pass",
                    current_result="fail",
                    score_delta=score_delta,
                    config_hash_before=state.current_config_hash,
                    config_hash_after=new_config_hash,
                )
                drifts.append(drift)
                state.active_drift_events.append(drift)

        return drifts

    @staticmethod
    def _calculate_severity(report: ComplianceReport, score_delta: Decimal) -> DriftSeverity:
        """Determine overall drift severity from critical failures and score change."""
        if report.critical_failures or abs(float(score_delta)) > 20:
            return DriftSeverity.CRITICAL
        elif abs(float(score_delta)) > 10:
            return DriftSeverity.HIGH
        elif abs(float(score_delta)) > 5:
            return DriftSeverity.MEDIUM
        else:
            return DriftSeverity.LOW

    @staticmethod
    def _map_severity(rule_severity: RuleSeverity, overall_severity: DriftSeverity) -> DriftSeverity:
        """Map rule severity to drift severity."""
        if rule_severity.value in DriftSeverity._value2member_map_:
            return DriftSeverity(rule_severity.value)
        return overall_severity
