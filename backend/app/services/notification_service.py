"""
Notification service for in-app and external event delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from app.infrastructure.database.repositories import NotificationRepository
from app.infrastructure.messaging.broker import publish_domain_event

log = structlog.get_logger(__name__)


class NotificationService:
    """Create, query, and update notification lifecycle state."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = NotificationRepository(db)

    async def create_notification(
        self,
        *,
        tenant_id: str,
        event_type: str,
        title: str,
        message: str,
        notification_type: NotificationType,
        user_id: UUID | None = None,
        incident_id: UUID | None = None,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        payload: dict[str, Any] | None = None,
    ) -> Notification:
        notification = await self.repo.create(
            tenant_id=tenant_id,
            event_type=event_type,
            title=title,
            message=message,
            notification_type=notification_type,
            user_id=user_id,
            incident_id=incident_id,
            channel=channel,
            status=NotificationStatus.PENDING,
            payload=payload or {},
        )

        await self._dispatch(notification)
        return notification

    async def _dispatch(self, notification: Notification) -> None:
        """Dispatch notification event and update status best-effort."""
        try:
            await publish_domain_event(
                "notification.created",
                {
                    "notification_id": str(notification.id),
                    "tenant_id": notification.tenant_id,
                    "event_type": notification.event_type,
                    "channel": notification.channel.value,
                    "user_id": str(notification.user_id) if notification.user_id else None,
                    "incident_id": str(notification.incident_id) if notification.incident_id else None,
                },
            )
            notification.status = NotificationStatus.SENT
            notification.delivery_error = None
        except Exception as exc:
            notification.status = NotificationStatus.FAILED
            notification.delivery_error = str(exc)
            log.error("notifications.dispatch.failed", notification_id=str(notification.id), error=str(exc))
        await self.db.flush()

    async def list_for_user(
        self,
        tenant_id: str,
        user_id: UUID,
        *,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Notification]:
        return await self.repo.list_for_user(
            tenant_id,
            user_id,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )

    async def mark_read(self, notification_id: UUID, user_id: UUID, tenant_id: str) -> Notification | None:
        notification = await self.repo.get_by_id(notification_id)
        if not notification:
            return None
        if notification.tenant_id != tenant_id or notification.user_id != user_id:
            return None

        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        notification.status = NotificationStatus.READ
        await self.db.flush()
        return notification
