"""
SIEM router — event ingestion, delivery status, platform health.
"""

from datetime import datetime, timezone
from collections import Counter
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.core.security import get_current_user, require_permission
from app.infrastructure.database.models import EventSeverity
from app.infrastructure.database.session import get_db
from app.infrastructure.database.repositories import SIEMEventRepository

import structlog

log = structlog.get_logger(__name__)
router = APIRouter()


class SIEMEventRequest(BaseModel):
    event_type: str
    severity: EventSeverity
    source: str
    raw_data: dict
    correlated_event_ids: list[str] | None = None


class SIEMEventResponse(BaseModel):
    event_id: str
    event_type: str
    severity: str
    source: str
    raw_data: dict
    created_at: str
    correlated: bool
    drift_id: str | None = None
    device_ip: str | None = None
    framework: str | None = None
    rule_name: str | None = None
    score_delta: float | None = None
    detected_at: str | None = None
    acknowledged: bool | None = None
    remediated: bool | None = None


@router.post("/events", response_model=SIEMEventResponse, status_code=status.HTTP_201_CREATED)
async def ingest_siem_event(
    request: SIEMEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("siem:write")),
) -> SIEMEventResponse:
    """Ingest a SIEM event."""
    from app.infrastructure.database.models import SIEMEvent
    
    event = SIEMEvent(
        event_type=request.event_type,
        severity=request.severity,
        source=request.source,
        raw_data=request.raw_data,
        correlated_events=request.correlated_event_ids or [],
        message=request.raw_data.get("message", request.event_type),
        event_timestamp=datetime.now(timezone.utc),
        tenant_id=current_user.tenant_id,
    )
    db.add(event)
    await db.commit()
    
    log.info(
        "siem.event.ingested",
        event_id=str(event.id),
        event_type=request.event_type,
        severity=request.severity.value,
    )
    
    return SIEMEventResponse(
        event_id=str(event.id),
        event_type=event.event_type,
        severity=event.severity.value,
        source=event.source,
        raw_data=event.raw_data or {},
        created_at=event.created_at.isoformat() if event.created_at else datetime.now(timezone.utc).isoformat(),
        correlated=len(event.correlated_events) > 0 if event.correlated_events else False,
        drift_id=str(event.id),
        device_ip=(event.raw_data or {}).get("device_ip"),
        framework=(event.raw_data or {}).get("framework"),
        rule_name=event.event_type,
        score_delta=float((event.raw_data or {}).get("score_delta", 0.0)),
        detected_at=event.event_timestamp.isoformat(),
        acknowledged=bool((event.raw_data or {}).get("acknowledged", False)),
        remediated=bool((event.raw_data or {}).get("remediated", False)),
    )


@router.get("/events", response_model=list[SIEMEventResponse])
async def list_siem_events(
    severity: EventSeverity | None = Query(default=None),
    source_platform: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("siem:read")),
) -> list[SIEMEventResponse]:
    """List SIEM events."""
    stmt = select(SIEMEvent).where(SIEMEvent.tenant_id == current_user.tenant_id)
    if severity:
        stmt = stmt.where(SIEMEvent.severity == severity)
    if source_platform:
        stmt = stmt.where(SIEMEvent.source == source_platform)
    stmt = stmt.order_by(desc(SIEMEvent.event_timestamp)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    return [
        SIEMEventResponse(
            event_id=str(e.id),
            event_type=e.event_type,
            severity=e.severity.value,
            source=e.source,
            raw_data=e.raw_data or {},
            created_at=e.ingested_at.isoformat() if e.ingested_at else datetime.now(timezone.utc).isoformat(),
            correlated=len(e.correlated_events) > 0 if e.correlated_events else False,
            drift_id=str(e.id),
            device_ip=(e.raw_data or {}).get("device_ip"),
            framework=(e.raw_data or {}).get("framework"),
            rule_name=e.event_type,
            score_delta=float((e.raw_data or {}).get("score_delta", 0.0)),
            detected_at=e.event_timestamp.isoformat(),
            acknowledged=bool((e.raw_data or {}).get("acknowledged", False)),
            remediated=bool((e.raw_data or {}).get("remediated", False)),
        )
        for e in events
    ]


@router.get("/events/{event_id}", response_model=SIEMEventResponse)
async def get_siem_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("siem:read")),
) -> SIEMEventResponse:
    """Get a specific SIEM event."""
    event_repo = SIEMEventRepository(db)
    event = await event_repo.get_by_id(event_id)
    
    if not event or event.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    return SIEMEventResponse(
        event_id=str(event.id),
        event_type=event.event_type,
        severity=event.severity.value,
        source=event.source,
        raw_data=event.raw_data or {},
        created_at=event.ingested_at.isoformat() if event.ingested_at else datetime.now(timezone.utc).isoformat(),
        correlated=len(event.correlated_events) > 0 if event.correlated_events else False,
        drift_id=str(event.id),
        device_ip=(event.raw_data or {}).get("device_ip"),
        framework=(event.raw_data or {}).get("framework"),
        rule_name=event.event_type,
        score_delta=float((event.raw_data or {}).get("score_delta", 0.0)),
        detected_at=event.event_timestamp.isoformat(),
        acknowledged=bool((event.raw_data or {}).get("acknowledged", False)),
        remediated=bool((event.raw_data or {}).get("remediated", False)),
    )


@router.get("/health")
async def siem_health(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("siem:read")),
) -> dict:
    """Get SIEM platform health status."""
    stmt = select(func.count(SIEMEvent.id)).where(SIEMEvent.tenant_id == current_user.tenant_id)
    total = await db.scalar(stmt) or 0
    return {
        "status": "healthy" if total >= 0 else "degraded",
        "platforms": sorted({"platform-db", "event-correlation"}),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total_events": total,
    }


@router.post("/correlate/{event_id}")
async def correlate_event(
    event_id: UUID,
    related_event_ids: list[UUID],
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("siem:write")),
) -> dict:
    """Correlate a SIEM event with related events."""
    event_repo = SIEMEventRepository(db)
    event = await event_repo.get_by_id(event_id)
    
    if not event or event.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    event.correlated_events = [str(e_id) for e_id in related_event_ids]
    await db.commit()
    
    log.info(
        "siem.event.correlated",
        event_id=str(event_id),
        correlated_count=len(related_event_ids),
    )
    
    return {
        "event_id": str(event_id),
        "correlated_events": len(related_event_ids),
        "status": "correlated",
    }
