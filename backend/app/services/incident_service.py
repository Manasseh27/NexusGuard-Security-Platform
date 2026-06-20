"""
Incident management service with lifecycle, assignment, comments, timeline, and notifications.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    EventSeverity,
    Incident,
    IncidentComment,
    IncidentStatus,
    IncidentTimeline,
    NotificationChannel,
    NotificationType,
)
from app.infrastructure.database.repositories import (
    IncidentCommentRepository,
    IncidentRepository,
    IncidentTimelineRepository,
)
from app.services.notification_service import NotificationService

log = structlog.get_logger(__name__)


class IncidentService:
    """Enterprise incident lifecycle orchestration."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.incident_repo = IncidentRepository(db)
        self.comment_repo = IncidentCommentRepository(db)
        self.timeline_repo = IncidentTimelineRepository(db)
        self.notifications = NotificationService(db)

    async def _next_incident_key(self, tenant_id: str) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        stmt = select(func.count(Incident.id)).where(Incident.tenant_id == tenant_id)
        total = (await self.db.scalar(stmt)) or 0
        return f"INC-{today}-{int(total) + 1:05d}"

    async def create_incident(
        self,
        *,
        title: str,
        description: str,
        severity: EventSeverity,
        tenant_id: str,
        created_by: UUID,
        source: str = "platform",
        device_id: UUID | None = None,
        finding_id: str | None = None,
        owner_id: UUID | None = None,
        assigned_to: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Incident:
        incident = await self.incident_repo.create(
            incident_key=await self._next_incident_key(tenant_id),
            title=title,
            description=description,
            severity=severity,
            status=IncidentStatus.NEW,
            source=source,
            device_id=device_id,
            finding_id=finding_id,
            created_by=created_by,
            owner_id=owner_id or created_by,
            assigned_to=assigned_to,
            tenant_id=tenant_id,
            custom_fields=metadata or {},
        )

        await self.add_timeline_entry(
            incident_id=incident.id,
            tenant_id=tenant_id,
            actor_id=created_by,
            event_type="incident.created",
            details={"status": incident.status.value, "severity": incident.severity.value},
        )

        if assigned_to:
            incident.status = IncidentStatus.ASSIGNED
            await self.add_timeline_entry(
                incident_id=incident.id,
                tenant_id=tenant_id,
                actor_id=created_by,
                event_type="incident.assigned",
                details={"assigned_to": str(assigned_to)},
            )
            await self.notifications.create_notification(
                tenant_id=tenant_id,
                user_id=assigned_to,
                incident_id=incident.id,
                event_type="incident.assigned",
                title=f"Incident assigned: {incident.incident_key}",
                message=incident.title,
                notification_type=NotificationType.INCIDENT,
                channel=NotificationChannel.IN_APP,
                payload={"incident_id": str(incident.id), "incident_key": incident.incident_key},
            )

        log.info("incident.created", incident_id=str(incident.id), incident_key=incident.incident_key)
        return incident

    async def list_incidents(
        self,
        tenant_id: str,
        *,
        status: IncidentStatus | None = None,
        assigned_to: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Incident]:
        return await self.incident_repo.list_by_tenant(
            tenant_id,
            status=status,
            assigned_to=assigned_to,
            limit=limit,
            offset=offset,
        )

    async def get_incident(self, incident_id: UUID, tenant_id: str) -> Incident | None:
        incident = await self.incident_repo.get_by_id(incident_id)
        if not incident or incident.tenant_id != tenant_id:
            return None
        return incident

    async def assign_incident(
        self,
        incident_id: UUID,
        tenant_id: str,
        assigned_to: UUID,
        actor_id: UUID,
    ) -> Incident | None:
        incident = await self.get_incident(incident_id, tenant_id)
        if not incident:
            return None

        incident.assigned_to = assigned_to
        incident.status = IncidentStatus.ASSIGNED
        await self.add_timeline_entry(
            incident_id=incident.id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            event_type="incident.assigned",
            details={"assigned_to": str(assigned_to)},
        )

        await self.notifications.create_notification(
            tenant_id=tenant_id,
            user_id=assigned_to,
            incident_id=incident.id,
            event_type="incident.assigned",
            title=f"Incident assigned: {incident.incident_key}",
            message=incident.title,
            notification_type=NotificationType.INCIDENT,
            channel=NotificationChannel.IN_APP,
            payload={"incident_id": str(incident.id), "incident_key": incident.incident_key},
        )

        await self.db.flush()
        return incident

    async def update_status(
        self,
        incident_id: UUID,
        tenant_id: str,
        status: IncidentStatus,
        actor_id: UUID,
    ) -> Incident | None:
        incident = await self.get_incident(incident_id, tenant_id)
        if not incident:
            return None

        incident.status = status
        if status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.now(timezone.utc)
        if status == IncidentStatus.CLOSED:
            incident.closed_at = datetime.now(timezone.utc)

        await self.add_timeline_entry(
            incident_id=incident.id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            event_type="incident.status_changed",
            details={"status": status.value},
        )

        if status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED) and incident.owner_id:
            await self.notifications.create_notification(
                tenant_id=tenant_id,
                user_id=incident.owner_id,
                incident_id=incident.id,
                event_type=f"incident.{status.value}",
                title=f"Incident {status.value}: {incident.incident_key}",
                message=incident.title,
                notification_type=NotificationType.INCIDENT,
                channel=NotificationChannel.IN_APP,
                payload={"incident_id": str(incident.id), "incident_key": incident.incident_key},
            )

        await self.db.flush()
        return incident

    async def add_comment(
        self,
        incident_id: UUID,
        tenant_id: str,
        user_id: UUID,
        comment: str,
        *,
        is_internal: bool = False,
    ) -> IncidentComment | None:
        incident = await self.get_incident(incident_id, tenant_id)
        if not incident:
            return None

        entry = await self.comment_repo.create(
            incident_id=incident_id,
            user_id=user_id,
            comment=comment,
            is_internal=is_internal,
            tenant_id=tenant_id,
        )
        await self.add_timeline_entry(
            incident_id=incident_id,
            tenant_id=tenant_id,
            actor_id=user_id,
            event_type="incident.comment_added",
            details={"is_internal": is_internal},
        )
        return entry

    async def add_timeline_entry(
        self,
        *,
        incident_id: UUID,
        tenant_id: str,
        actor_id: UUID | None,
        event_type: str,
        details: dict[str, Any] | None = None,
    ) -> IncidentTimeline:
        return await self.timeline_repo.create(
            incident_id=incident_id,
            actor_id=actor_id,
            event_type=event_type,
            details=details or {},
            tenant_id=tenant_id,
        )

    async def list_comments(self, incident_id: UUID, tenant_id: str, limit: int = 500) -> list[IncidentComment]:
        incident = await self.get_incident(incident_id, tenant_id)
        if not incident:
            return []
        return await self.comment_repo.list_by_incident(incident_id, limit=limit)

    async def list_timeline(self, incident_id: UUID, tenant_id: str, limit: int = 1000) -> list[IncidentTimeline]:
        incident = await self.get_incident(incident_id, tenant_id)
        if not incident:
            return []
        return await self.timeline_repo.list_by_incident(incident_id, limit=limit)
