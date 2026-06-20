"""
Incident management API router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.infrastructure.database.models import EventSeverity, IncidentStatus
from app.infrastructure.database.session import get_db
from app.services.incident_service import IncidentService

router = APIRouter()


class IncidentCreateRequest(BaseModel):
    title: str = Field(min_length=5, max_length=256)
    description: str = Field(min_length=10, max_length=10000)
    severity: EventSeverity
    source: str = Field(default="platform", max_length=128)
    device_id: UUID | None = None
    finding_id: str | None = Field(default=None, max_length=128)
    owner_id: UUID | None = None
    assigned_to: UUID | None = None


class IncidentUpdateStatusRequest(BaseModel):
    status: IncidentStatus


class IncidentAssignRequest(BaseModel):
    assigned_to: UUID


class IncidentCommentRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    is_internal: bool = False


class IncidentResponse(BaseModel):
    id: str
    incident_key: str
    title: str
    description: str
    severity: str
    status: str
    source: str
    device_id: str | None
    finding_id: str | None
    created_by: str | None
    assigned_to: str | None
    owner_id: str | None
    created_at: str
    updated_at: str
    resolved_at: str | None
    closed_at: str | None


def _incident_response(incident) -> IncidentResponse:
    return IncidentResponse(
        id=str(incident.id),
        incident_key=incident.incident_key,
        title=incident.title,
        description=incident.description,
        severity=incident.severity.value,
        status=incident.status.value,
        source=incident.source,
        device_id=str(incident.device_id) if incident.device_id else None,
        finding_id=incident.finding_id,
        created_by=str(incident.created_by) if incident.created_by else None,
        assigned_to=str(incident.assigned_to) if incident.assigned_to else None,
        owner_id=str(incident.owner_id) if incident.owner_id else None,
        created_at=incident.created_at.isoformat() if incident.created_at else datetime.now(timezone.utc).isoformat(),
        updated_at=incident.updated_at.isoformat() if incident.updated_at else datetime.now(timezone.utc).isoformat(),
        resolved_at=incident.resolved_at.isoformat() if incident.resolved_at else None,
        closed_at=incident.closed_at.isoformat() if incident.closed_at else None,
    )


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    request: IncidentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("incidents:write")),
) -> IncidentResponse:
    service = IncidentService(db)
    incident = await service.create_incident(
        title=request.title,
        description=request.description,
        severity=request.severity,
        source=request.source,
        device_id=request.device_id,
        finding_id=request.finding_id,
        owner_id=request.owner_id,
        assigned_to=request.assigned_to,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
    )
    await db.commit()
    return _incident_response(incident)


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    status: IncidentStatus | None = Query(default=None),
    assigned_to: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("incidents:read")),
) -> list[IncidentResponse]:
    service = IncidentService(db)
    incidents = await service.list_incidents(
        current_user.tenant_id,
        status=status,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )
    return [_incident_response(incident) for incident in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("incidents:read")),
) -> IncidentResponse:
    service = IncidentService(db)
    incident = await service.get_incident(incident_id, current_user.tenant_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return _incident_response(incident)


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
async def update_incident_status(
    incident_id: UUID,
    request: IncidentUpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("incidents:write")),
) -> IncidentResponse:
    service = IncidentService(db)
    incident = await service.update_status(
        incident_id,
        current_user.tenant_id,
        request.status,
        current_user.id,
    )
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    await db.commit()
    return _incident_response(incident)


@router.patch("/{incident_id}/assign", response_model=IncidentResponse)
async def assign_incident(
    incident_id: UUID,
    request: IncidentAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("incidents:assign")),
) -> IncidentResponse:
    service = IncidentService(db)
    incident = await service.assign_incident(
        incident_id=incident_id,
        tenant_id=current_user.tenant_id,
        assigned_to=request.assigned_to,
        actor_id=current_user.id,
    )
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    await db.commit()
    return _incident_response(incident)


@router.post("/{incident_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_incident_comment(
    incident_id: UUID,
    request: IncidentCommentRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("incidents:write")),
) -> dict:
    service = IncidentService(db)
    comment = await service.add_comment(
        incident_id=incident_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        comment=request.comment,
        is_internal=request.is_internal,
    )
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    await db.commit()
    return {
        "id": str(comment.id),
        "incident_id": str(comment.incident_id),
        "user_id": str(comment.user_id) if comment.user_id else None,
        "comment": comment.comment,
        "is_internal": comment.is_internal,
        "created_at": comment.created_at.isoformat() if comment.created_at else datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{incident_id}/comments")
async def list_incident_comments(
    incident_id: UUID,
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("incidents:read")),
) -> list[dict]:
    service = IncidentService(db)
    comments = await service.list_comments(incident_id, current_user.tenant_id, limit=limit)
    return [
        {
            "id": str(c.id),
            "incident_id": str(c.incident_id),
            "user_id": str(c.user_id) if c.user_id else None,
            "comment": c.comment,
            "is_internal": c.is_internal,
            "created_at": c.created_at.isoformat() if c.created_at else datetime.now(timezone.utc).isoformat(),
        }
        for c in comments
    ]


@router.get("/{incident_id}/timeline")
async def incident_timeline(
    incident_id: UUID,
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("incidents:read")),
) -> list[dict]:
    service = IncidentService(db)
    timeline = await service.list_timeline(incident_id, current_user.tenant_id, limit=limit)
    return [
        {
            "id": str(entry.id),
            "incident_id": str(entry.incident_id),
            "event_type": entry.event_type,
            "actor_id": str(entry.actor_id) if entry.actor_id else None,
            "details": entry.details,
            "created_at": entry.created_at.isoformat() if entry.created_at else datetime.now(timezone.utc).isoformat(),
        }
        for entry in timeline
    ]
