"""
Compliance Service
Handles compliance evaluation, scoring, and remediation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    ComplianceFramework,
    ComplianceResult,
    ComplianceScore,
    DriftEvent,
    RemediationJob,
    RemediationStatus,
    RuleSeverity,
    Device,
    DriftSeverity,
)
from app.infrastructure.database.repositories import (
    ComplianceResultRepository,
    ComplianceScoreRepository,
    DriftEventRepository,
    RemediationJobRepository,
)

log = structlog.get_logger(__name__)


class ComplianceService:
    """Compliance evaluation and scoring."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.score_repo = ComplianceScoreRepository(db)
        self.result_repo = ComplianceResultRepository(db)
        self.drift_repo = DriftEventRepository(db)
        self.remediation_repo = RemediationJobRepository(db)

    async def record_compliance_result(
        self,
        device_id: UUID,
        framework: ComplianceFramework,
        rule_id: str,
        rule_name: str,
        result: str,
        severity: RuleSeverity,
        message: str | None = None,
        evidence: dict[str, Any] | None = None,
        remediation_guidance: str | None = None,
        tenant_id: str = "default",
    ) -> ComplianceResult:
        """Record a single compliance rule result."""
        comp_result = await self.result_repo.create(
            device_id=device_id,
            framework=framework,
            rule_id=rule_id,
            rule_name=rule_name,
            result=result,
            severity=severity,
            message=message,
            evidence=evidence or {},
            remediation_guidance=remediation_guidance,
            tenant_id=tenant_id,
        )
        return comp_result

    async def calculate_compliance_score(
        self,
        device_id: UUID,
        framework: ComplianceFramework,
        tenant_id: str = "default",
    ) -> ComplianceScore:
        """Calculate overall compliance score for device against framework."""
        results = await self.result_repo.list_by_device_framework(device_id, framework)

        if not results:
            score = Decimal("0")
            weighted_score = Decimal("0")
            pass_count = 0
            fail_count = 0
            error_count = 0
        else:
            pass_count = sum(1 for r in results if r.result == "pass")
            fail_count = sum(1 for r in results if r.result == "fail")
            error_count = sum(1 for r in results if r.result == "error")
            warning_count = sum(1 for r in results if r.result == "warn")
            critical_count = sum(1 for r in results if r.result == "fail" and r.severity == RuleSeverity.CRITICAL)

            total = len(results)
            score = Decimal(pass_count) / Decimal(total) * Decimal("100") if total > 0 else Decimal("0")

            # Weighted score: account for severity
            severity_weights = {
                RuleSeverity.CRITICAL: Decimal("10"),
                RuleSeverity.HIGH: Decimal("7"),
                RuleSeverity.MEDIUM: Decimal("5"),
                RuleSeverity.LOW: Decimal("2"),
                RuleSeverity.INFORMATIONAL: Decimal("1"),
            }
            total_possible = sum(severity_weights.get(r.severity, Decimal("1")) for r in results)
            total_weighted = sum(
                severity_weights.get(r.severity, Decimal("1"))
                for r in results
                if r.result == "pass"
            )
            weighted_score = (
                total_weighted / total_possible * Decimal("100")
                if total_possible > 0
                else Decimal("0")
            )

        compliance_score = await self.score_repo.create(
            device_id=device_id,
            framework=framework,
            overall_score=score,
            weighted_score=weighted_score,
            compliance_percentage=score,
            pass_count=pass_count,
            fail_count=fail_count,
            error_count=error_count,
            warning_count=warning_count,
            critical_failures=sum(1 for r in results if r.result == "fail" and r.severity == RuleSeverity.CRITICAL),
            tenant_id=tenant_id,
        )
        return compliance_score

    async def detect_drift(
        self,
        device_id: UUID,
        framework: ComplianceFramework,
        previous_result: str,
        current_result: str,
        rule_id: str,
        rule_name: str,
        severity: DriftSeverity,
        score_delta: Decimal,
        config_hash_before: str,
        config_hash_after: str,
        tenant_id: str = "default",
    ) -> DriftEvent | None:
        """Detect and record compliance drift."""
        if previous_result == current_result:
            return None  # No drift

        drift = await self.drift_repo.create(
            device_id=device_id,
            framework=framework,
            rule_id=rule_id,
            rule_name=rule_name,
            severity=severity,
            previous_result=previous_result,
            current_result=current_result,
            score_delta=score_delta,
            config_hash_before=config_hash_before,
            config_hash_after=config_hash_after,
            acknowledged=False,
            remediated=False,
            tenant_id=tenant_id,
        )
        log.info(
            "compliance.drift.detected",
            device_id=str(device_id),
            rule_id=rule_id,
            severity=severity.value,
            previous=previous_result,
            current=current_result,
        )
        return drift

    async def list_unacknowledged_drifts(self, device_id: UUID | None = None, limit: int = 100) -> list[DriftEvent]:
        """List unacknowledged drift events."""
        return await self.drift_repo.list_unacknowledged(device_id, limit)

    async def acknowledge_drift(self, drift_id: UUID, user_id: UUID) -> DriftEvent | None:
        """Acknowledge a drift event."""
        drift = await self.drift_repo.get_by_id(drift_id)
        if not drift:
            return None

        drift.acknowledged = True
        drift.acknowledged_at = datetime.now(timezone.utc)
        drift.acknowledged_by = user_id
        await self.db.flush()
        log.info("compliance.drift.acknowledged", drift_id=str(drift_id), user_id=str(user_id))
        return drift

    async def create_remediation_job(
        self,
        device_id: UUID,
        remediation_type: str,
        target_config: dict[str, Any],
        drift_event_id: UUID | None = None,
        created_by: UUID | None = None,
        tenant_id: str = "default",
    ) -> RemediationJob:
        """Create a remediation job."""
        job = await self.remediation_repo.create(
            device_id=device_id,
            drift_event_id=drift_event_id,
            status=RemediationStatus.PENDING,
            remediation_type=remediation_type,
            target_config=target_config,
            created_by=created_by,
            tenant_id=tenant_id,
        )
        log.info(
            "remediation.job.created",
            job_id=str(job.id),
            device_id=str(device_id),
            type=remediation_type,
        )
        return job

    async def start_remediation_job(self, job_id: UUID) -> RemediationJob | None:
        """Mark remediation job as in-progress."""
        job = await self.remediation_repo.get_by_id(job_id)
        if not job:
            return None

        job.status = RemediationStatus.IN_PROGRESS
        job.started_at = datetime.now(timezone.utc)
        await self.db.flush()
        log.info("remediation.job.started", job_id=str(job_id))
        return job

    async def complete_remediation_job(
        self,
        job_id: UUID,
        success: bool = True,
        output: str | None = None,
        error_message: str | None = None,
    ) -> RemediationJob | None:
        """Mark remediation job as complete."""
        job = await self.remediation_repo.get_by_id(job_id)
        if not job:
            return None

        job.status = RemediationStatus.SUCCEEDED if success else RemediationStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.execution_output = output
        job.error_message = error_message
        await self.db.flush()
        log.info(
            "remediation.job.completed",
            job_id=str(job_id),
            status="success" if success else "failed",
        )
        return job

    async def list_pending_remediation_jobs(self, limit: int = 100) -> list[RemediationJob]:
        """List pending remediation jobs ready for execution."""
        return await self.remediation_repo.list_pending(limit)

    async def get_compliance_score_latest(
        self,
        device_id: UUID,
        framework: ComplianceFramework,
    ) -> ComplianceScore | None:
        """Get most recent compliance score for device/framework."""
        return await self.score_repo.get_latest_for_device_framework(device_id, framework)

    async def get_compliance_history(
        self,
        device_id: UUID,
        limit: int = 100,
    ) -> list[ComplianceScore]:
        """Get compliance score history."""
        return await self.score_repo.list_by_device(device_id, limit)

    async def get_failures_by_device(
        self,
        device_id: UUID,
        limit: int = 100,
    ) -> list[ComplianceResult]:
        """Get all failed compliance checks for a device."""
        return await self.result_repo.list_failures_by_device(device_id, limit)

    async def list_all_unacknowledged_drifts(self, limit: int = 100) -> list[DriftEvent]:
        """List all unacknowledged drift events across all devices."""
        # Note: In production, would paginate properly. For now, get all.
        return await self.drift_repo.list_unacknowledged(None, limit)

    async def get_all_latest_scores_by_tenant(self, tenant_id: str) -> list[ComplianceScore]:
        """Get latest compliance scores for all devices in a tenant."""
        from sqlalchemy import select, func
        
        # Get the latest score for each device/framework combination
        stmt = (
            select(ComplianceScore)
            .where(ComplianceScore.tenant_id == tenant_id)
            .order_by(ComplianceScore.device_id, ComplianceScore.framework, ComplianceScore.created_at.desc())
            .distinct(ComplianceScore.device_id, ComplianceScore.framework)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
