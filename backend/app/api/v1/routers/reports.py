"""
Reports router — compliance reports, executive summaries.
"""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_permission
from app.infrastructure.database.models import ComplianceFramework
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.database.session import get_db
from app.services.device_service import DeviceService
from app.services.compliance_service import ComplianceService

import structlog

log = structlog.get_logger(__name__)
router = APIRouter()


class ReportResponse(BaseModel):
    report_id: str
    report_type: str
    framework: str | None
    status: str
    created_at: str
    generated_by: str


def _report_key(report_id: str) -> str:
    return f"reports:{report_id}"


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    report_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("reports:read")),
) -> list[ReportResponse]:
    """List available reports."""
    compliance_service = ComplianceService(db)
    scores = await compliance_service.get_all_latest_scores_by_tenant(current_user.tenant_id)

    framework_latest: dict[str, tuple[datetime, int]] = {}
    for score in scores:
        framework = score.framework.value
        generated_at = score.generated_at or datetime.now(timezone.utc)
        current = framework_latest.get(framework)
        if current is None or generated_at > current[0]:
            framework_latest[framework] = (generated_at, int(score.device_id.int % 10_000_000))

    return [
        ReportResponse(
            report_id=f"{framework}-{ts.isoformat()}",
            report_type="compliance_summary",
            framework=framework,
            status="completed",
            created_at=ts.isoformat(),
            generated_by=current_user.username,
        )
        for framework, (ts, _) in sorted(framework_latest.items())
    ]


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    report_type: str = Query(default="compliance_summary"),
    framework: str | None = Query(default="cis"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("reports:write")),
) -> dict:
    """Generate a compliance report."""
    report_id = str(uuid4())
    
    device_service = DeviceService(db)
    compliance_service = ComplianceService(db)
    
    # Get fleet status
    fleet = await device_service.fleet_status_summary(current_user.tenant_id)
    
    # Get compliance data
    fw = ComplianceFramework.CIS if framework == "cis" else ComplianceFramework.NIST_CSF
    scores = await compliance_service.get_all_latest_scores_by_tenant(current_user.tenant_id)
    scores = [s for s in scores if s.framework == fw]

    average_score = sum(float(s.overall_score) for s in scores) / len(scores) if scores else 0.0
    devices_compliant = sum(1 for s in scores if float(s.overall_score) >= 90)

    report_payload = {
        "report_id": report_id,
        "report_type": report_type,
        "framework": framework,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": str(current_user.username),
        "tenant_id": current_user.tenant_id,
        "summary": {
            "total_devices": fleet["total_devices"],
            "avg_compliance_score": average_score,
            "devices_compliant": devices_compliant,
            "devices_at_risk": max(0, len(scores) - devices_compliant),
        },
    }

    redis_client = get_redis()
    if redis_client is not None:
        await redis_client.setex(_report_key(report_id), 7 * 24 * 60 * 60, json.dumps(report_payload))
    
    log.info(
        "reports.generate.requested",
        report_id=report_id,
        report_type=report_type,
        framework=framework,
        user_id=str(current_user.id),
    )
    
    return {
        "report_id": report_id,
        "status": "completed",
        "type": report_type,
        "framework": framework,
        "estimated_completion": datetime.now(timezone.utc).isoformat(),
        "preview": report_payload["summary"],
    }


@router.get("/{report_id}")
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("reports:read")),
) -> dict:
    """Get a specific report."""
    redis_client = get_redis()
    if redis_client is not None:
        raw_value = await redis_client.get(_report_key(str(report_id)))
        if raw_value:
            return json.loads(raw_value)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


@router.post("/{report_id}/download")
async def download_report(
    report_id: UUID,
    format: str = Query(default="pdf"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("reports:read")),
) -> dict:
    """Download a report in specified format."""
    log.info(
        "reports.download.requested",
        report_id=str(report_id),
        format=format,
        user_id=str(current_user.id),
    )
    
    return {
        "report_id": str(report_id),
        "format": format,
        "download_url": f"/api/v1/reports/{report_id}/file?format={format}",
        "expires_in_seconds": 3600,
    }


@router.get("/{report_id}/file")
async def get_report_file(
    report_id: UUID,
    format: str = Query(default="json"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("reports:read")),
) -> dict:
    """Return the generated report payload for download/viewing."""
    redis_client = get_redis()
    if redis_client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    raw_value = await redis_client.get(_report_key(str(report_id)))
    if not raw_value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    report = json.loads(raw_value)
    report["format"] = format
    return report
