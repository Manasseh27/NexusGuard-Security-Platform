"""
Repository pattern — data access layer for all domain models.
Async-compatible with SQLAlchemy 2.0 async engine.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infrastructure.database.models import (
    AuditLog,
    ComplianceException,
    ComplianceFramework,
    ComplianceResult,
    ComplianceScore,
    Device,
    DeviceCredentials,
    DeviceMonitoringState,
    DriftEvent,
    Incident,
    IncidentComment,
    IncidentStatus,
    IncidentTimeline,
    Notification,
    NotificationStatus,
    RemediationJob,
    SIEMEvent,
    User,
    UserRole,
)

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, id: UUID) -> T | None:
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **kwargs) -> T:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, id: UUID, **kwargs) -> T | None:
        instance = await self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            await self.session.flush()
        return instance

    async def delete(self, id: UUID) -> bool:
        instance = await self.get_by_id(id)
        if instance:
            self.session.delete(instance)
            await self.session.flush()
            return True
        return False


class UserRepository(BaseRepository[User]):
    """User CRUD + authentication queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(self.model).where(self.model.username == username)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(self.model).where(self.model.email == email)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_tenant_and_role(self, tenant_id: str, role: UserRole) -> list[User]:
        stmt = select(self.model).where(
            and_(self.model.tenant_id == tenant_id, self.model.role == role)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_tenant(self, tenant_id: str, limit: int = 100, offset: int = 0) -> list[User]:
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class DeviceRepository(BaseRepository[Device]):
    """Device CRUD + filtering queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Device)

    async def get_by_device_id(self, device_id: str) -> Device | None:
        stmt = select(self.model).where(self.model.device_id == device_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_ip_address(self, ip_address: str) -> Device | None:
        stmt = select(self.model).where(self.model.ip_address == ip_address)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_tenant(self, tenant_id: str, limit: int = 100, offset: int = 0) -> list[Device]:
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .options(joinedload(self.model.monitoring_state))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.unique().scalars().all()

    async def list_by_site(self, tenant_id: str, site: str, limit: int = 100, offset: int = 0) -> list[Device]:
        stmt = (
            select(self.model)
            .where(and_(self.model.tenant_id == tenant_id, self.model.site == site))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_device_type(self, tenant_id: str, device_type: str, limit: int = 100, offset: int = 0) -> list[Device]:
        stmt = (
            select(self.model)
            .where(and_(self.model.tenant_id == tenant_id, self.model.device_type == device_type))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_tenant(self, tenant_id: str) -> int:
        stmt = select(func.count()).select_from(self.model).where(self.model.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0


class DeviceCredentialsRepository(BaseRepository[DeviceCredentials]):
    """Device credentials management."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DeviceCredentials)

    async def get_by_name(self, tenant_id: str, name: str) -> DeviceCredentials | None:
        stmt = select(self.model).where(
            and_(self.model.tenant_id == tenant_id, self.model.name == name)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_tenant(self, tenant_id: str) -> list[DeviceCredentials]:
        stmt = select(self.model).where(self.model.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class DeviceMonitoringStateRepository(BaseRepository[DeviceMonitoringState]):
    """Device monitoring state queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DeviceMonitoringState)

    async def get_by_device_id(self, device_id: UUID) -> DeviceMonitoringState | None:
        stmt = select(self.model).where(self.model.device_id == device_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_unhealthy_devices(self, tenant_id: str) -> list[DeviceMonitoringState]:
        stmt = (
            select(self.model)
            .join(Device)
            .where(
                and_(
                    Device.tenant_id == tenant_id,
                    self.model.monitoring_state.in_(["drifting", "degraded", "unreachable"]),
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_due_for_poll(self, limit: int = 100) -> list[DeviceMonitoringState]:
        from datetime import datetime, timezone

        stmt = (
            select(self.model)
            .join(Device)
            .where(and_(Device.is_enabled == True, self.model.next_poll_at <= datetime.now(timezone.utc)))
            .order_by(self.model.next_poll_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ComplianceScoreRepository(BaseRepository[ComplianceScore]):
    """Compliance score queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ComplianceScore)

    async def get_latest_for_device_framework(
        self, device_id: UUID, framework: ComplianceFramework
    ) -> ComplianceScore | None:
        stmt = (
            select(self.model)
            .where(
                and_(
                    self.model.device_id == device_id,
                    self.model.framework == framework,
                )
            )
            .order_by(desc(self.model.generated_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_device(
        self, device_id: UUID, limit: int = 100
    ) -> list[ComplianceScore]:
        stmt = (
            select(self.model)
            .where(self.model.device_id == device_id)
            .order_by(desc(self.model.generated_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_tenant_and_framework(
        self, tenant_id: str, framework: ComplianceFramework, limit: int = 1000
    ) -> list[ComplianceScore]:
        stmt = (
            select(self.model)
            .where(
                and_(
                    self.model.tenant_id == tenant_id,
                    self.model.framework == framework,
                )
            )
            .order_by(desc(self.model.generated_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ComplianceResultRepository(BaseRepository[ComplianceResult]):
    """Compliance rule results."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ComplianceResult)

    async def list_by_device_framework(
        self, device_id: UUID, framework: ComplianceFramework, limit: int = 1000
    ) -> list[ComplianceResult]:
        stmt = (
            select(self.model)
            .where(
                and_(
                    self.model.device_id == device_id,
                    self.model.framework == framework,
                )
            )
            .order_by(desc(self.model.evaluated_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_failures_by_device(self, device_id: UUID, limit: int = 100) -> list[ComplianceResult]:
        stmt = (
            select(self.model)
            .where(and_(self.model.device_id == device_id, self.model.result.in_(["fail", "error"])))
            .order_by(desc(self.model.evaluated_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class DriftEventRepository(BaseRepository[DriftEvent]):
    """Drift event queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DriftEvent)

    async def list_unacknowledged(self, device_id: UUID | None = None, limit: int = 100) -> list[DriftEvent]:
        stmt = select(self.model).where(self.model.acknowledged == False).order_by(desc(self.model.detected_at)).limit(limit)
        if device_id:
            stmt = stmt.where(self.model.device_id == device_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_unacknowledged_by_severity(
        self, severity: str, limit: int = 100
    ) -> list[DriftEvent]:
        stmt = (
            select(self.model)
            .where(and_(self.model.acknowledged == False, self.model.severity == severity))
            .order_by(desc(self.model.detected_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_active_by_device(self, device_id: UUID) -> int:
        stmt = select(func.count()).select_from(self.model).where(
            and_(self.model.device_id == device_id, self.model.acknowledged == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0


class RemediationJobRepository(BaseRepository[RemediationJob]):
    """Remediation job queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RemediationJob)

    async def list_pending(self, limit: int = 100) -> list[RemediationJob]:
        stmt = (
            select(self.model)
            .where(self.model.status == "pending")
            .order_by(self.model.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_device(self, device_id: UUID, limit: int = 100) -> list[RemediationJob]:
        stmt = (
            select(self.model)
            .where(self.model.device_id == device_id)
            .order_by(desc(self.model.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class AuditLogRepository(BaseRepository[AuditLog]):
    """Audit log queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)

    async def list_by_user(self, user_id: UUID, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(desc(self.model.timestamp))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_action(self, action: str, limit: int = 100) -> list[AuditLog]:
        stmt = (
            select(self.model)
            .where(self.model.action == action)
            .order_by(desc(self.model.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_resource(self, resource_type: str, resource_id: str, limit: int = 100) -> list[AuditLog]:
        stmt = (
            select(self.model)
            .where(and_(self.model.resource_type == resource_type, self.model.resource_id == resource_id))
            .order_by(desc(self.model.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class SIEMEventRepository(BaseRepository[SIEMEvent]):
    """SIEM event queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SIEMEvent)

    async def list_by_severity(
        self, tenant_id: str, severity: str, limit: int = 100, offset: int = 0
    ) -> list[SIEMEvent]:
        stmt = (
            select(self.model)
            .where(and_(self.model.tenant_id == tenant_id, self.model.severity == severity))
            .order_by(desc(self.model.event_timestamp))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_uncorrelated(self, limit: int = 100) -> list[SIEMEvent]:
        stmt = (
            select(self.model)
            .where(self.model.is_correlated == False)
            .order_by(self.model.ingested_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ComplianceExceptionRepository(BaseRepository[ComplianceException]):
    """Compliance exception queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ComplianceException)

    async def list_active_for_device(self, device_id: UUID) -> list[ComplianceException]:
        from datetime import datetime, timezone

        stmt = (
            select(self.model)
            .where(
                and_(
                    self.model.device_id == device_id,
                    self.model.is_active == True,
                    self.model.expires_at > datetime.now(timezone.utc),
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class IncidentRepository(BaseRepository[Incident]):
    """Incident lifecycle and assignment queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Incident)

    async def get_by_incident_key(self, incident_key: str) -> Incident | None:
        stmt = select(self.model).where(self.model.incident_key == incident_key)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        status: IncidentStatus | None = None,
        assigned_to: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Incident]:
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .order_by(desc(self.model.created_at))
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        if assigned_to is not None:
            stmt = stmt.where(self.model.assigned_to == assigned_to)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class IncidentCommentRepository(BaseRepository[IncidentComment]):
    """Incident comment queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IncidentComment)

    async def list_by_incident(self, incident_id: UUID, limit: int = 500) -> list[IncidentComment]:
        stmt = (
            select(self.model)
            .where(self.model.incident_id == incident_id)
            .order_by(self.model.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class IncidentTimelineRepository(BaseRepository[IncidentTimeline]):
    """Incident timeline queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IncidentTimeline)

    async def list_by_incident(self, incident_id: UUID, limit: int = 1000) -> list[IncidentTimeline]:
        stmt = (
            select(self.model)
            .where(self.model.incident_id == incident_id)
            .order_by(self.model.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class NotificationRepository(BaseRepository[Notification]):
    """Notification queue and delivery state queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Notification)

    async def list_for_user(
        self,
        tenant_id: str,
        user_id: UUID,
        *,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Notification]:
        stmt = (
            select(self.model)
            .where(and_(self.model.tenant_id == tenant_id, self.model.user_id == user_id))
            .order_by(desc(self.model.created_at))
            .limit(limit)
            .offset(offset)
        )
        if unread_only:
            stmt = stmt.where(self.model.is_read == False)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_pending(self, limit: int = 500) -> list[Notification]:
        stmt = (
            select(self.model)
            .where(self.model.status == NotificationStatus.PENDING)
            .order_by(self.model.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
