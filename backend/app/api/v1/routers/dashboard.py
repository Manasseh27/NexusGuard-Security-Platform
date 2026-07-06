"""
Dashboard summary API — single endpoint for all live dashboard data.
Returns fleet KPIs, per-framework compliance scores, incident counts,
audit event count, 24-hour compliance trend, and recent activity feed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.infrastructure.database.models import (
    AuditLog,
    ComplianceFramework,
    ComplianceScore,
    DriftEvent,
    Incident,
    IncidentStatus,
    EventSeverity,
)
from app.infrastructure.database.session import get_db
from app.services.compliance_service import ComplianceService
from app.services.device_service import DeviceService

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("monitoring:read")),
) -> dict[str, Any]:
    """
    Single-call dashboard summary.
    Returns fleet status, per-framework scores, incident KPIs,
    audit count, 24h compliance trend, and recent activity.
    """
    tenant_id = current_user.tenant_id
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)

    compliance_svc = ComplianceService(db)
    device_svc = DeviceService(db)

    # ── Fleet status ───────────────────────────────────────────────────────────
    fleet = await device_svc.fleet_status_summary(tenant_id)

    # ── Per-framework scores ───────────────────────────────────────────────────
    all_scores = await compliance_svc.get_all_latest_scores_by_tenant(tenant_id)

    framework_scores: dict[str, list[float]] = {}
    for score in all_scores:
        fw = score.framework.value
        framework_scores.setdefault(fw, []).append(float(score.overall_score))

    frameworks = [
        {
            "id": fw,
            "avg_score": round(sum(scores) / len(scores), 1),
            "device_count": len(scores),
            "devices_compliant": sum(1 for s in scores if s >= 90),
            "devices_at_risk": sum(1 for s in scores if 60 <= s < 90),
            "devices_critical": sum(1 for s in scores if s < 60),
        }
        for fw, scores in framework_scores.items()
    ]

    # ── Incident KPIs ──────────────────────────────────────────────────────────
    open_statuses = [
        IncidentStatus.NEW,
        IncidentStatus.ASSIGNED,
        IncidentStatus.INVESTIGATING,
        IncidentStatus.CONTAINED,
    ]

    total_incidents_result = await db.scalar(
        select(func.count(Incident.id)).where(Incident.tenant_id == tenant_id)
    )
    open_incidents_result = await db.scalar(
        select(func.count(Incident.id)).where(
            Incident.tenant_id == tenant_id,
            Incident.status.in_(open_statuses),
        )
    )
    critical_incidents_result = await db.scalar(
        select(func.count(Incident.id)).where(
            Incident.tenant_id == tenant_id,
            Incident.severity == EventSeverity.CRITICAL,
            Incident.status.in_(open_statuses),
        )
    )

    # ── Audit event count (last 24h) ───────────────────────────────────────────
    audit_24h_result = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.timestamp >= since_24h,
        )
    )
    audit_total_result = await db.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id)
    )

    # ── 24h compliance trend (hourly avg score buckets) ───────────────────────
    scores_24h_result = await db.execute(
        select(ComplianceScore)
        .where(
            ComplianceScore.tenant_id == tenant_id,
            ComplianceScore.generated_at >= since_24h,
        )
        .order_by(ComplianceScore.generated_at.asc())
    )
    scores_24h = scores_24h_result.scalars().all()

    # Bucket into hourly slots
    hourly: dict[int, list[float]] = {}
    for score in scores_24h:
        if score.generated_at:
            hour_key = int((score.generated_at - since_24h).total_seconds() // 3600)
            hourly.setdefault(hour_key, []).append(float(score.overall_score))

    trend = []
    for h in range(24):
        t = since_24h + timedelta(hours=h)
        bucket = hourly.get(h, [])
        avg = round(sum(bucket) / len(bucket), 1) if bucket else None
        trend.append({
            "time": t.strftime("%H:00"),
            "score": avg,
            "hour": h,
        })

    # ── Recent activity feed (last 10 audit entries + last 5 incidents) ────────
    recent_audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(desc(AuditLog.timestamp))
        .limit(8)
    )
    recent_audit = recent_audit_result.scalars().all()

    recent_incidents_result = await db.execute(
        select(Incident)
        .where(Incident.tenant_id == tenant_id)
        .order_by(desc(Incident.created_at))
        .limit(5)
    )
    recent_incidents = recent_incidents_result.scalars().all()

    activity = []
    for entry in recent_audit:
        activity.append({
            "type": "audit",
            "id": str(entry.id),
            "action": entry.action,
            "resource_type": entry.resource_type,
            "outcome": entry.status,
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else now.isoformat(),
        })
    for inc in recent_incidents:
        activity.append({
            "type": "incident",
            "id": str(inc.id),
            "title": inc.title,
            "severity": inc.severity.value,
            "status": inc.status.value,
            "timestamp": inc.created_at.isoformat() if inc.created_at else now.isoformat(),
        })
    activity.sort(key=lambda x: x["timestamp"], reverse=True)

    # ── Health check data ──────────────────────────────────────────────────────
    from app.infrastructure.database.session import check_db_health
    from app.infrastructure.cache.redis_client import check_redis_health
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()

    return {
        "fleet": fleet,
        "frameworks": frameworks,
        "incidents": {
            "total": int(total_incidents_result or 0),
            "open": int(open_incidents_result or 0),
            "critical_open": int(critical_incidents_result or 0),
        },
        "audit": {
            "total": int(audit_total_result or 0),
            "last_24h": int(audit_24h_result or 0),
        },
        "trend": trend,
        "recent_activity": activity[:12],
        "services": {
            "api": True,
            "database": db_ok,
            "cache": redis_ok,
        },
        "generated_at": now.isoformat(),
    }
