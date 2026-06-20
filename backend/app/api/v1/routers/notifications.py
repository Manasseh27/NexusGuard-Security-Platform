"""
Notification API router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.infrastructure.database.models import NotificationChannel, NotificationType
from app.infrastructure.database.session import get_db
from app.services.notification_service import NotificationService

router = APIRouter()


class NotificationCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=256)
    message: str = Field(min_length=3, max_length=4000)
    event_type: str = Field(min_length=3, max_length=64)
    notification_type: NotificationType
    channel: NotificationChannel = NotificationChannel.IN_APP
    user_id: UUID | None = None
    incident_id: UUID | None = None
    payload: dict = {}


class NotificationResponse(BaseModel):
    id: str
    event_type: str
    title: str
    message: str
    notification_type: str
    channel: str
    status: str
    is_read: bool
    read_at: str | None
    user_id: str | None
    incident_id: str | None
    created_at: str


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    request: NotificationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("notifications:write")),
) -> NotificationResponse:
    service = NotificationService(db)
    notification = await service.create_notification(
        tenant_id=current_user.tenant_id,
        event_type=request.event_type,
        title=request.title,
        message=request.message,
        notification_type=request.notification_type,
        channel=request.channel,
        user_id=request.user_id,
        incident_id=request.incident_id,
        payload=request.payload,
    )
    await db.commit()

    return NotificationResponse(
        id=str(notification.id),
        event_type=notification.event_type,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type.value,
        channel=notification.channel.value,
        status=notification.status.value,
        is_read=notification.is_read,
        read_at=notification.read_at.isoformat() if notification.read_at else None,
        user_id=str(notification.user_id) if notification.user_id else None,
        incident_id=str(notification.incident_id) if notification.incident_id else None,
        created_at=notification.created_at.isoformat() if notification.created_at else datetime.now(timezone.utc).isoformat(),
    )


@router.get("", response_model=list[NotificationResponse])
async def list_my_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("notifications:read")),
) -> list[NotificationResponse]:
    service = NotificationService(db)
    notifications = await service.list_for_user(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return [
        NotificationResponse(
            id=str(item.id),
            event_type=item.event_type,
            title=item.title,
            message=item.message,
            notification_type=item.notification_type.value,
            channel=item.channel.value,
            status=item.status.value,
            is_read=item.is_read,
            read_at=item.read_at.isoformat() if item.read_at else None,
            user_id=str(item.user_id) if item.user_id else None,
            incident_id=str(item.incident_id) if item.incident_id else None,
            created_at=item.created_at.isoformat() if item.created_at else datetime.now(timezone.utc).isoformat(),
        )
        for item in notifications
    ]


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("notifications:read")),
) -> NotificationResponse:
    service = NotificationService(db)
    notification = await service.mark_read(notification_id, current_user.id, current_user.tenant_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.commit()

    return NotificationResponse(
        id=str(notification.id),
        event_type=notification.event_type,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type.value,
        channel=notification.channel.value,
        status=notification.status.value,
        is_read=notification.is_read,
        read_at=notification.read_at.isoformat() if notification.read_at else None,
        user_id=str(notification.user_id) if notification.user_id else None,
        incident_id=str(notification.incident_id) if notification.incident_id else None,
        created_at=notification.created_at.isoformat() if notification.created_at else datetime.now(timezone.utc).isoformat(),
    )
