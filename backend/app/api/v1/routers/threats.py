"""
Threat intelligence router.
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.core.security import get_current_user, require_permission
from app.infrastructure.database.models import SIEMEvent
from app.infrastructure.database.session import get_db

import structlog

log = structlog.get_logger(__name__)
router = APIRouter()


class ThreatIndicatorResponse(BaseModel):
    indicator_id: str
    indicator_type: str  # ip, domain, hash, url
    value: str
    severity: str  # critical, high, medium, low
    source: str
    discovered_at: str
    last_seen: str
    id: str | None = None
    indicator: str | None = None
    type: str | None = None


class CVEResponse(BaseModel):
    cve_id: str
    title: str
    description: str
    severity: str
    cvss_score: float
    affected_products: list[str]
    published_at: str
    id: str | None = None
    indicator: str | None = None
    type: str | None = None
    last_seen: str | None = None


@router.get("/indicators", response_model=list[ThreatIndicatorResponse])
async def list_indicators(
    indicator_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("threats:read")),
) -> list[ThreatIndicatorResponse]:
    """List threat indicators."""
    stmt = select(SIEMEvent).where(SIEMEvent.tenant_id == current_user.tenant_id)
    if indicator_type:
        stmt = stmt.where(SIEMEvent.event_type.ilike(f"%{indicator_type}%"))
    if severity:
        stmt = stmt.where(SIEMEvent.severity == severity)
    stmt = stmt.order_by(desc(SIEMEvent.event_timestamp)).limit(limit)
    events = (await db.execute(stmt)).scalars().all()

    indicators: list[ThreatIndicatorResponse] = []
    for event in events:
        raw_indicator = event.raw_data.get("indicator") if isinstance(event.raw_data, dict) else None
        indicator_value = raw_indicator or event.raw_data.get("value") if isinstance(event.raw_data, dict) else event.message
        indicators.append(
            ThreatIndicatorResponse(
                indicator_id=str(event.id),
                indicator_type=(event.raw_data.get("indicator_type") if isinstance(event.raw_data, dict) else None) or event.event_type,
                value=str(indicator_value or event.message),
                severity=event.severity.value,
                source=event.source,
                discovered_at=event.ingested_at.isoformat(),
                last_seen=event.event_timestamp.isoformat(),
                id=str(event.id),
                indicator=str(indicator_value or event.message),
                type=(event.raw_data.get("indicator_type") if isinstance(event.raw_data, dict) else None) or event.event_type,
            )
        )

    return indicators


@router.get("/cves", response_model=list[CVEResponse])
async def list_cves(
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("threats:read")),
) -> list[CVEResponse]:
    """List CVEs affecting the infrastructure."""
    stmt = select(SIEMEvent).where(SIEMEvent.tenant_id == current_user.tenant_id)
    if severity:
        stmt = stmt.where(SIEMEvent.severity == severity)
    stmt = stmt.where(SIEMEvent.event_type.ilike("%cve%") | SIEMEvent.raw_data.has_key("cve_id"))
    stmt = stmt.order_by(desc(SIEMEvent.event_timestamp)).limit(limit)
    events = (await db.execute(stmt)).scalars().all()

    cves: list[CVEResponse] = []
    for event in events:
        cve_id = event.raw_data.get("cve_id") if isinstance(event.raw_data, dict) else None
        title = event.raw_data.get("title") if isinstance(event.raw_data, dict) else None
        description = event.raw_data.get("description") if isinstance(event.raw_data, dict) else None
        affected_products = event.raw_data.get("affected_products") if isinstance(event.raw_data, dict) else None
        cvss_score = float(event.raw_data.get("cvss_score", 0.0)) if isinstance(event.raw_data, dict) else 0.0
        cves.append(
            CVEResponse(
                cve_id=str(cve_id or event.event_type),
                title=str(title or event.message),
                description=str(description or event.message),
                severity=event.severity.value,
                cvss_score=cvss_score,
                affected_products=list(affected_products or []),
                published_at=event.event_timestamp.isoformat(),
                id=str(event.id),
                indicator=str(cve_id or event.event_type),
                type="cve",
                last_seen=event.event_timestamp.isoformat(),
            )
        )

    return cves


@router.get("/summary")
async def threat_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("threats:read")),
) -> dict:
    """Get threat intelligence summary."""
    total_indicators = await db.scalar(
        select(func.count(SIEMEvent.id)).where(SIEMEvent.tenant_id == current_user.tenant_id)
    ) or 0
    critical_cves = await db.scalar(
        select(func.count(SIEMEvent.id)).where(
            SIEMEvent.tenant_id == current_user.tenant_id,
            SIEMEvent.severity == "critical",
            SIEMEvent.event_type.ilike("%cve%"),
        )
    ) or 0
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    recently_discovered = await db.scalar(
        select(func.count(SIEMEvent.id)).where(
            SIEMEvent.tenant_id == current_user.tenant_id,
            SIEMEvent.ingested_at >= recent_cutoff,
        )
    ) or 0
    sources = await db.execute(
        select(SIEMEvent.source).where(SIEMEvent.tenant_id == current_user.tenant_id).distinct()
    )
    return {
        "total_indicators": int(total_indicators),
        "total_cves": int(total_indicators),
        "critical_cves": int(critical_cves),
        "recently_discovered": int(recently_discovered),
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source_feeds": sorted({row[0] for row in sources.all() if row[0]}),
    }
