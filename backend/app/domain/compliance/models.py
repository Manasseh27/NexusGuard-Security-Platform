"""
Compliance domain models — shared data structures for monitoring, drift, and evaluation.
Extracted from continuous_monitor.py for reusability across services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from app.domain.compliance.engine.compliance_engine import ComplianceFramework, RuleSeverity


class DriftSeverity(str, Enum):
    """Severity levels for compliance drift events."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MonitoringState(str, Enum):
    """Device monitoring states — health indicators."""
    HEALTHY = "healthy"
    DRIFTING = "drifting"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    REMEDIATING = "remediating"


@dataclass
class DriftEvent:
    """Compliance drift event — detected when config or score changes."""
    drift_id: str = field(default_factory=lambda: str(uuid4()))
    device_id: str = ""
    device_ip: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    framework: str = ""
    rule_id: str = ""
    rule_name: str = ""
    severity: DriftSeverity = DriftSeverity.MEDIUM
    previous_result: str = ""
    current_result: str = ""
    score_delta: Decimal = Decimal("0")
    config_hash_before: str = ""
    config_hash_after: str = ""
    acknowledged: bool = False
    remediated: bool = False
    remediation_job_id: str | None = None


@dataclass
class DeviceMonitoringState:
    """Device monitoring state — tracks polling, scores, drifts, and health."""
    device_id: str
    device_ip: str
    device_type: str
    last_polled: datetime | None = None
    last_successful: datetime | None = None
    current_config_hash: str = ""
    current_score: Decimal = Decimal("0")
    baseline_score: Decimal | None = None
    monitoring_state: MonitoringState = MonitoringState.HEALTHY
    consecutive_failures: int = 0
    active_drift_events: list[DriftEvent] = field(default_factory=list)
    frameworks: list[ComplianceFramework] = field(default_factory=list)
    poll_interval: int = 300  # seconds
    next_poll_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ComplianceSnapshot:
    """Point-in-time compliance snapshot — stored in history."""
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    device_id: str = ""
    framework: str = ""
    score: Decimal = Decimal("0")
    config_hash: str = ""
    pass_count: int = 0
    fail_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    report_data: dict[str, Any] = field(default_factory=dict)
