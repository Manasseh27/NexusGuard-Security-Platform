"""
Device Management Service
Handles device CRUD, status tracking, and monitoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    Device,
    DeviceMonitoringState,
    DeviceType,
    MonitoringState,
)
from app.infrastructure.database.repositories import (
    DeviceMonitoringStateRepository,
    DeviceRepository,
)

log = structlog.get_logger(__name__)


class DeviceService:
    """Device management and monitoring."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.device_repo = DeviceRepository(db)
        self.state_repo = DeviceMonitoringStateRepository(db)

    async def create_device(
        self,
        device_id: str | None = None,
        hostname: str = "",
        ip_address: str = "",
        device_type: DeviceType = DeviceType.GENERIC,
        site: str = "",
        tags: list[str] | None = None,
        tenant_id: str = "default",
        credentials_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Device:
        """Create a new managed device."""
        device_id = device_id or str(uuid4())

        # Check for duplicates
        if await self.device_repo.get_by_device_id(device_id):
            raise ValueError(f"Device '{device_id}' already exists")
        if await self.device_repo.get_by_ip_address(ip_address):
            raise ValueError(f"IP address '{ip_address}' already registered")

        device = await self.device_repo.create(
            device_id=device_id,
            hostname=hostname,
            ip_address=ip_address,
            device_type=device_type,
            site=site,
            tags=tags or [],
            tenant_id=tenant_id,
            credentials_id=credentials_id,
            metadata=metadata or {},
            is_enabled=True,
        )

        # Create initial monitoring state
        await self.state_repo.create(
            device_id=device.id,
            monitoring_state=MonitoringState.HEALTHY,
            current_score=0,
            current_config_hash="",
            consecutive_failures=0,
            active_drift_count=0,
            poll_interval=300,
            next_poll_at=datetime.now(timezone.utc),
            frameworks=[],
        )

        log.info("device.created", device_id=device_id, hostname=hostname, ip_address=ip_address, site=site)
        return device

    async def get_device(self, device_uuid: UUID) -> Device | None:
        """Get device by UUID."""
        return await self.device_repo.get_by_id(device_uuid)

    async def get_device_by_id(self, device_id: str) -> Device | None:
        """Get device by device_id string."""
        return await self.device_repo.get_by_device_id(device_id)

    async def get_device_by_ip(self, ip_address: str) -> Device | None:
        """Get device by IP address."""
        return await self.device_repo.get_by_ip_address(ip_address)

    async def list_devices_by_tenant(self, tenant_id: str, limit: int = 100, offset: int = 0) -> list[Device]:
        """List all devices in a tenant."""
        return await self.device_repo.list_by_tenant(tenant_id, limit, offset)

    async def list_devices_by_site(self, tenant_id: str, site: str, limit: int = 100, offset: int = 0) -> list[Device]:
        """List devices at a specific site."""
        return await self.device_repo.list_by_site(tenant_id, site, limit, offset)

    async def list_devices_by_type(
        self, tenant_id: str, device_type: str, limit: int = 100, offset: int = 0
    ) -> list[Device]:
        """List devices of a specific type."""
        return await self.device_repo.list_by_device_type(tenant_id, device_type, limit, offset)

    async def count_devices_by_tenant(self, tenant_id: str) -> int:
        """Count total devices in tenant."""
        return await self.device_repo.count_by_tenant(tenant_id)

    async def update_device(self, device_uuid: UUID, **kwargs) -> Device | None:
        """Update device properties."""
        # Remove read-only fields
        kwargs.pop("id", None)
        kwargs.pop("created_at", None)
        kwargs.pop("device_id", None)  # Don't allow changing device_id
        kwargs["updated_at"] = datetime.now(timezone.utc)

        device = await self.device_repo.update(device_uuid, **kwargs)
        if device:
            log.info("device.updated", device_uuid=str(device_uuid))
        return device

    async def delete_device(self, device_uuid: UUID) -> bool:
        """Delete a device."""
        result = await self.device_repo.delete(device_uuid)
        if result:
            log.info("device.deleted", device_uuid=str(device_uuid))
        return result

    async def enable_device(self, device_uuid: UUID) -> Device | None:
        """Enable device monitoring."""
        return await self.update_device(device_uuid, is_enabled=True)

    async def disable_device(self, device_uuid: UUID) -> Device | None:
        """Disable device monitoring."""
        return await self.update_device(device_uuid, is_enabled=False)

    # ── Device state management ────────────────────────────────────────────────

    async def get_device_state(self, device_uuid: UUID) -> DeviceMonitoringState | None:
        """Get current monitoring state for device."""
        return await self.state_repo.get_by_device_id(device_uuid)

    async def update_device_state(
        self,
        device_uuid: UUID,
        monitoring_state: MonitoringState | None = None,
        current_score: float | None = None,
        config_hash: str | None = None,
        last_polled: datetime | None = None,
        last_successful: datetime | None = None,
        consecutive_failures: int | None = None,
        active_drift_count: int | None = None,
        next_poll_at: datetime | None = None,
    ) -> DeviceMonitoringState | None:
        """Update device monitoring state."""
        state = await self.state_repo.get_by_device_id(device_uuid)
        if not state:
            return None

        update_data = {}
        if monitoring_state is not None:
            update_data["monitoring_state"] = monitoring_state
        if current_score is not None:
            update_data["current_score"] = current_score
        if config_hash is not None:
            update_data["current_config_hash"] = config_hash
        if last_polled is not None:
            update_data["last_polled"] = last_polled
        if last_successful is not None:
            update_data["last_successful"] = last_successful
        if consecutive_failures is not None:
            update_data["consecutive_failures"] = consecutive_failures
        if active_drift_count is not None:
            update_data["active_drift_count"] = active_drift_count
        if next_poll_at is not None:
            update_data["next_poll_at"] = next_poll_at
        update_data["updated_at"] = datetime.now(timezone.utc)

        state_id = state.id
        updated = await self.state_repo.update(state_id, **update_data)
        return updated

    async def list_unhealthy_devices(self, tenant_id: str) -> list[DeviceMonitoringState]:
        """List devices in drifting, degraded, or unreachable state."""
        states = await self.state_repo.list_unhealthy_devices(tenant_id)
        return states

    async def list_devices_due_for_poll(self, limit: int = 100) -> list[DeviceMonitoringState]:
        """List devices that need polling soon."""
        return await self.state_repo.list_due_for_poll(limit)

    async def fleet_status_summary(self, tenant_id: str) -> dict[str, Any]:
        """Get fleet-wide status summary."""
        devices = await self.device_repo.list_by_tenant(tenant_id, limit=10000)
        total = len(devices)

        if total == 0:
            return {
                "total_devices": 0,
                "healthy": 0,
                "drifting": 0,
                "degraded": 0,
                "unreachable": 0,
                "average_compliance_score": 0.0,
                "fleet_health_pct": 0.0,
                "active_drift_events": 0,
            }

        states = [d.monitoring_state for d in devices if d.monitoring_state]
        state_counts = {
            "healthy": sum(1 for s in states if s.monitoring_state == MonitoringState.HEALTHY),
            "drifting": sum(1 for s in states if s.monitoring_state == MonitoringState.DRIFTING),
            "degraded": sum(1 for s in states if s.monitoring_state == MonitoringState.DEGRADED),
            "unreachable": sum(1 for s in states if s.monitoring_state == MonitoringState.UNREACHABLE),
        }
        avg_score = (
            sum(s.current_score for s in states if s.current_score) / len([s for s in states if s.current_score])
            if any(s.current_score for s in states)
            else 0.0
        )
        active_drifts = sum(s.active_drift_count for s in states)
        health_pct = (state_counts["healthy"] / total * 100) if total > 0 else 0.0

        return {
            "total_devices": total,
            "healthy": state_counts["healthy"],
            "drifting": state_counts["drifting"],
            "degraded": state_counts["degraded"],
            "unreachable": state_counts["unreachable"],
            "average_compliance_score": float(avg_score),
            "fleet_health_pct": health_pct,
            "active_drift_events": active_drifts,
        }
