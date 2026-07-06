"""
Compliance API Router (database-backed)
Endpoints: framework evaluation, history, scoring, drift, exceptions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_permission
from app.core.dependencies import get_compliance_orchestrator
from app.infrastructure.database.models import ComplianceFramework, RuleSeverity
from app.infrastructure.database.session import get_db
from app.services.compliance_service import ComplianceService
from app.services.device_service import DeviceService
from app.workers.tasks import run_bulk_compliance

log = structlog.get_logger(__name__)
router = APIRouter()



# ── Request / Response models ──────────────────────────────────────────────────

class EvaluateDeviceRequest(BaseModel):
    device_id: UUID
    framework: ComplianceFramework = ComplianceFramework.CIS
    force_refresh: bool = False


class BulkEvaluateRequest(BaseModel):
    device_ids: list[UUID] = Field(..., min_length=1, max_length=500)
    framework: ComplianceFramework = ComplianceFramework.CIS
    notify_on_failure: bool = True


class ComplianceResultRequest(BaseModel):
    rule_id: str
    rule_name: str
    result: str  # "pass" | "fail" | "error"
    severity: RuleSeverity
    message: str
    evidence: dict[str, Any] = {}


class ComplianceScoreResponse(BaseModel):
    device_id: str
    framework: str
    overall_score: float
    weighted_score: float
    pass_count: int
    fail_count: int
    error_count: int
    evaluated_at: str
    baseline_delta: float | None = None


class DriftEventResponse(BaseModel):
    drift_id: str
    device_id: str
    framework: str
    rule_id: str
    rule_name: str
    severity: str
    previous_result: str
    current_result: str
    score_delta: float
    detected_at: str
    acknowledged: bool
    remediated: bool


class FrameworkSummaryResponse(BaseModel):
    framework: str
    total_devices: int
    avg_score: float
    devices_compliant: int    # >= 90%
    devices_at_risk: int      # 60-89%
    devices_critical: int     # < 60%
    total_critical_findings: int


class ComplianceExceptionRequest(BaseModel):
    device_id: UUID
    rule_id: str
    justification: str = Field(..., min_length=20, max_length=2000)
    expiry_days: int = Field(default=90, ge=1, le=365)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/frameworks",
    summary="List supported compliance frameworks",
    response_model=list[dict[str, str]],
)
async def list_frameworks(
    current_user=Depends(require_permission("compliance:read")),
) -> list[dict[str, str]]:
    """Get list of supported compliance frameworks."""
    frameworks = [
        {
            "id": ComplianceFramework.CIS.value,
            "name": "CIS Cisco IOS Benchmark",
            "description": "CIS Level 1 & 2 hardening standards",
        },
        {
            "id": ComplianceFramework.NIST_CSF.value,
            "name": "NIST CSF",
            "description": "NIST Cybersecurity Framework v1.1",
        },
        {
            "id": ComplianceFramework.NIST_800_53.value,
            "name": "NIST SP 800-53",
            "description": "NIST SP 800-53 Rev 5 Security Controls",
        },
        {
            "id": ComplianceFramework.ISO_27001.value,
            "name": "ISO/IEC 27001",
            "description": "ISO/IEC 27001:2022 Information Security",
        },
        {
            "id": ComplianceFramework.PCI_DSS.value,
            "name": "PCI DSS",
            "description": "PCI DSS v4.0 Payment Card Security",
        },
    ]
    return frameworks


@router.post(
    "/evaluate",
    summary="Evaluate compliance for a device",
    response_model=ComplianceScoreResponse,
)
async def evaluate_device(
    request: EvaluateDeviceRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("compliance:evaluate")),
) -> ComplianceScoreResponse:
    """Evaluate device compliance against a framework."""
    device_service = DeviceService(db)
    compliance_service = ComplianceService(db)

    # Verify device exists and belongs to tenant
    device = await device_service.get_device(request.device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    log.info(
        "compliance.evaluate.requested",
        device_id=str(request.device_id),
        framework=request.framework.value,
        user_id=str(current_user.id),
    )

    # Get latest score from database
    score = await compliance_service.get_compliance_score_latest(
        device.id,
        request.framework,
    )

    if not score:
        orchestrator = get_compliance_orchestrator()
        device_config = {
            "running_config": device.custom_fields.get("running_config", ""),
            "baseline_config": device.custom_fields.get("baseline_config"),
            "site": device.site,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "device_type": device.device_type.value,
        }
        report = await orchestrator.evaluate_device(
            device_id=device.id,
            device_config=device_config,
            device_metadata={
                "device_id": device.device_id,
                "hostname": device.hostname,
                "site": device.site,
                "tenant_id": device.tenant_id,
            },
            frameworks=[request.framework],
        )

        for result in report.results:
            await compliance_service.record_compliance_result(
                device_id=device.id,
                framework=request.framework,
                rule_id=result.rule_id,
                rule_name=result.rule_name,
                result=result.result.value,
                severity=result.severity,
                message="; ".join(result.findings) if result.findings else None,
                evidence=result.evidence,
                remediation_guidance="\n".join(result.remediation_steps) if result.remediation_steps else None,
                tenant_id=device.tenant_id,
            )

        score = await compliance_service.calculate_compliance_score(
            device_id=device.id,
            framework=request.framework,
            tenant_id=device.tenant_id,
        )

        await db.commit()
        return ComplianceScoreResponse(
            device_id=str(request.device_id),
            framework=request.framework.value,
            overall_score=float(score.overall_score),
            weighted_score=float(score.weighted_score),
            pass_count=score.pass_count,
            fail_count=score.fail_count,
            error_count=score.error_count,
            evaluated_at=score.generated_at.isoformat(),
            baseline_delta=float(score.baseline_delta) if score.baseline_delta is not None else None,
        )

    return ComplianceScoreResponse(
        device_id=str(device.id),
        framework=score.framework.value,
        overall_score=float(score.overall_score),
        weighted_score=float(score.weighted_score),
        pass_count=score.pass_count,
        fail_count=score.fail_count,
        error_count=score.error_count,
        evaluated_at=score.generated_at.isoformat() if score.generated_at else datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/evaluate/bulk",
    summary="Bulk evaluate compliance for multiple devices",
    status_code=status.HTTP_202_ACCEPTED,
)
async def bulk_evaluate(
    request: BulkEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("compliance:evaluate")),
) -> dict[str, Any]:
    """Queue bulk compliance evaluation for multiple devices."""
    device_service = DeviceService(db)

    # Verify all devices exist and belong to tenant
    for device_id in request.device_ids:
        device = await device_service.get_device(device_id)
        if not device or device.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device {device_id} not found",
            )

    log.info(
        "compliance.bulk_evaluate.queued",
        device_count=len(request.device_ids),
        framework=request.framework.value,
        user_id=str(current_user.id),
    )

    task = run_bulk_compliance.apply_async(
        args=[[str(device_id) for device_id in request.device_ids], [request.framework.value]],
        queue="compliance",
    )

    return {
        "job_id": task.id,
        "device_count": len(request.device_ids),
        "framework": request.framework.value,
        "status": "queued",
        "message": f"Bulk evaluation queued for {len(request.device_ids)} devices",
    }


@router.get(
    "/devices/{device_id}/score",
    summary="Get latest compliance score for a device",
    response_model=ComplianceScoreResponse,
)
async def get_device_score(
    device_id: UUID,
    framework: ComplianceFramework = Query(default=ComplianceFramework.CIS),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("compliance:read")),
) -> ComplianceScoreResponse:
    """Get the latest compliance score for a device."""
    device_service = DeviceService(db)
    compliance_service = ComplianceService(db)

    device = await device_service.get_device(device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    score = await compliance_service.get_compliance_score_latest(device.id, framework)
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No compliance score available for this device",
        )

    return ComplianceScoreResponse(
        device_id=str(device.id),
        framework=score.framework.value,
        overall_score=float(score.overall_score),
        weighted_score=float(score.weighted_score),
        pass_count=score.pass_count,
        fail_count=score.fail_count,
        error_count=score.error_count,
        evaluated_at=score.generated_at.isoformat() if score.generated_at else datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/devices/{device_id}/results",
    summary="Get detailed compliance results for a device",
    response_model=list[dict[str, Any]],
)
async def get_device_results(
    device_id: UUID,
    framework: ComplianceFramework = Query(default=ComplianceFramework.CIS),
    limit: int = Query(default=100, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("compliance:read")),
) -> list[dict[str, Any]]:
    """Get detailed compliance results for a device."""
    device_service = DeviceService(db)
    compliance_service = ComplianceService(db)

    device = await device_service.get_device(device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    results = await compliance_service.get_failures_by_device(device.id, limit)

    return [
        {
            "rule_id": r.rule_id,
            "rule_name": r.rule_name,
            "framework": r.framework.value,
            "result": r.result,
            "severity": r.severity.value,
            "message": r.message,
            "evidence": r.evidence or {},
            "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else datetime.now(timezone.utc).isoformat(),
        }
        for r in results
    ]


@router.get(
    "/drift/active",
    summary="List all active compliance drift events",
)
async def active_drift_events(
    severity: RuleSeverity | None = Query(default=None),
    framework: ComplianceFramework | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("compliance:read")),
) -> dict[str, Any]:
    """Get all unacknowledged drift events across the tenant."""
    compliance_service = ComplianceService(db)

    drifts = await compliance_service.list_all_unacknowledged_drifts(limit)

    # Filter by severity and framework if specified
    if severity:
        drifts = [d for d in drifts if d.severity == severity]
    if framework:
        drifts = [d for d in drifts if d.framework == framework]

    # Sort by severity (critical first), then by detected_at
    severity_order = {
        RuleSeverity.CRITICAL: 0,
        RuleSeverity.HIGH: 1,
        RuleSeverity.MEDIUM: 2,
        RuleSeverity.LOW: 3,
    }

    drifts.sort(key=lambda d: (
        severity_order.get(d.severity, 4),
        d.detected_at or datetime.now(timezone.utc),
    ))

    return {
        "total": len(drifts),
        "returned": min(len(drifts), limit),
        "drifts": [
            {
                "drift_id": str(d.id),
                "device_id": str(d.device_id),
                "framework": d.framework.value,
                "rule_id": d.rule_id,
                "rule_name": d.rule_name,
                "severity": d.severity.value,
                "previous_result": d.previous_result,
                "current_result": d.current_result,
                "score_delta": float(d.score_delta) if d.score_delta else 0.0,
                "detected_at": d.detected_at.isoformat() if d.detected_at else datetime.now(timezone.utc).isoformat(),
                "acknowledged": d.acknowledged,
                "remediated": d.remediated,
            }
            for d in drifts[:limit]
        ],
    }


@router.post(
    "/drift/{drift_id}/acknowledge",
    summary="Acknowledge a drift event",
)
async def acknowledge_drift(
    drift_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("compliance:acknowledge")),
) -> dict[str, str]:
    """Mark a drift event as acknowledged."""
    compliance_service = ComplianceService(db)

    drift = await compliance_service.acknowledge_drift(drift_id, current_user.id)
    if not drift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drift event not found",
        )

    await db.commit()
    log.info(
        "compliance.drift.acknowledged",
        drift_id=str(drift_id),
        user_id=str(current_user.id),
    )

    return {"status": "acknowledged", "drift_id": str(drift_id)}


@router.post(
    "/exceptions",
    summary="Create a compliance exception",
    status_code=status.HTTP_201_CREATED,
)
async def create_exception(
    request: ComplianceExceptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("compliance:exception:create")),
) -> dict[str, Any]:
    """Create a compliance exception for a rule."""
    from app.infrastructure.database.models import ComplianceException

    device_service = DeviceService(db)
    device = await device_service.get_device(request.device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    expiry = datetime.now(timezone.utc) + timedelta(days=request.expiry_days)

    exception = ComplianceException(
        device_id=device.id,
        rule_id=request.rule_id,
        justification=request.justification,
        expires_at=expiry,
        is_active=True,
        tenant_id=current_user.tenant_id,
    )
    db.add(exception)
    await db.commit()

    log.info(
        "compliance.exception.created",
        device_id=str(request.device_id),
        rule_id=request.rule_id,
        user_id=str(current_user.id),
        expiry=expiry.isoformat(),
    )

    return {
        "exception_id": str(exception.id),
        "device_id": str(request.device_id),
        "rule_id": request.rule_id,
        "status": "active",
        "expiry": expiry.isoformat(),
        "created_by": current_user.username,
        "message": f"Exception created for rule {request.rule_id}",
    }


@router.get(
    "/fleet/summary",
    summary="Fleet-wide compliance summary",
)
async def fleet_summary(
    framework: ComplianceFramework | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("compliance:read")),
) -> dict[str, Any]:
    """Get fleet-wide compliance summary."""
    compliance_service = ComplianceService(db)
    device_service = DeviceService(db)

    # Get fleet status
    fleet_status = await device_service.fleet_status_summary(current_user.tenant_id)

    # Calculate avg compliance across all frameworks
    scores = await compliance_service.get_all_latest_scores_by_tenant(current_user.tenant_id)

    if framework:
        scores = [s for s in scores if s.framework == framework]

    avg_score = sum(float(s.overall_score) for s in scores) / len(scores) if scores else 0.0

    compliant = sum(1 for s in scores if float(s.overall_score) >= 90)
    at_risk = sum(1 for s in scores if 60 <= float(s.overall_score) < 90)
    critical = sum(1 for s in scores if float(s.overall_score) < 60)

    return {
        "fleet_health_pct": fleet_status["fleet_health_pct"],
        "avg_compliance_score": round(avg_score, 2),
        "total_devices": fleet_status["total_devices"],
        "devices_compliant": compliant,
        "devices_at_risk": at_risk,
        "devices_critical": critical,
        "active_drift_events": fleet_status["active_drift_events"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
