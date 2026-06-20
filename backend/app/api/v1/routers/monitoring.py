"""
Continuous Monitoring API Router
Endpoints: fleet status, device state, monitoring health.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_permission
from app.infrastructure.database.session import get_db
from app.services.device_service import DeviceService
from app.workers.tasks import run_compliance_eval

log = structlog.get_logger(__name__)
router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────────

class DeviceStateResponse(BaseModel):
    device_id: str
    device_ip: str
    device_type: str
    monitoring_state: str
    current_score: float
    baseline_score: float | None
    last_polled: str | None
    last_successful: str | None
    active_drift_count: int
    consecutive_failures: int
    poll_interval: int
    next_poll_at: str
    frameworks: list[str]


class FleetStatusResponse(BaseModel):
    total_devices: int
    healthy: int
    drifting: int
    unreachable: int
    degraded: int
    average_compliance_score: float
    fleet_health_pct: float
    active_drift_events: int
    monitoring_enabled: bool
    updated_at: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/fleet",
    summary="Fleet-wide monitoring summary",
    response_model=FleetStatusResponse,
)
async def fleet_status(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("monitoring:read")),
) -> FleetStatusResponse:
    """Get fleet-wide status summary."""
    from app.core.config import settings

    service = DeviceService(db)
    summary = await service.fleet_status_summary(current_user.tenant_id)

    return FleetStatusResponse(
        total_devices=summary["total_devices"],
        healthy=summary["healthy"],
        drifting=summary["drifting"],
        unreachable=summary["unreachable"],
        degraded=summary["degraded"],
        average_compliance_score=summary["average_compliance_score"],
        fleet_health_pct=summary["fleet_health_pct"],
        active_drift_events=summary["active_drift_events"],
        monitoring_enabled=True,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/devices",
    summary="List all monitored devices with current state",
    response_model=list[DeviceStateResponse],
)
async def list_monitored_devices(
    monitoring_state: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("monitoring:read")),
) -> list[DeviceStateResponse]:
    """List all devices with current monitoring state."""
    service = DeviceService(db)
    devices = await service.list_devices_by_tenant(current_user.tenant_id, limit, offset)

    result = []
    for device in devices:
        if not device.monitoring_state:
            continue
        state = device.monitoring_state
        if monitoring_state and state.monitoring_state.value != monitoring_state:
            continue

        result.append(
            DeviceStateResponse(
                device_id=device.device_id,
                device_ip=device.ip_address,
                device_type=device.device_type.value,
                monitoring_state=state.monitoring_state.value,
                current_score=float(state.current_score),
                baseline_score=float(state.baseline_score) if state.baseline_score else None,
                last_polled=state.last_polled.isoformat() if state.last_polled else None,
                last_successful=state.last_successful.isoformat() if state.last_successful else None,
                active_drift_count=state.active_drift_count,
                consecutive_failures=state.consecutive_failures,
                poll_interval=state.poll_interval,
                next_poll_at=state.next_poll_at.isoformat(),
                frameworks=state.frameworks,
            )
        )

    return result


@router.get(
    "/devices/{device_id}",
    summary="Get monitoring state for a specific device",
    response_model=DeviceStateResponse,
)
async def get_device_state(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("monitoring:read")),
) -> DeviceStateResponse:
    """Get monitoring state for a specific device."""
    service = DeviceService(db)
    device = await service.get_device(device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found",
        )

    if not device.monitoring_state:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Device monitoring state not initialized",
        )

    state = device.monitoring_state
    return DeviceStateResponse(
        device_id=device.device_id,
        device_ip=device.ip_address,
        device_type=device.device_type.value,
        monitoring_state=state.monitoring_state.value,
        current_score=float(state.current_score),
        baseline_score=float(state.baseline_score) if state.baseline_score else None,
        last_polled=state.last_polled.isoformat() if state.last_polled else None,
        last_successful=state.last_successful.isoformat() if state.last_successful else None,
        active_drift_count=state.active_drift_count,
        consecutive_failures=state.consecutive_failures,
        poll_interval=state.poll_interval,
        next_poll_at=state.next_poll_at.isoformat(),
        frameworks=state.frameworks,
    )


@router.post("/devices/{device_id}/poll", status_code=status.HTTP_202_ACCEPTED)
async def force_poll_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("monitoring:write")),
) -> dict[str, Any]:
    """Force immediate compliance poll for a device."""
    service = DeviceService(db)
    device = await service.get_device_by_id(device_id)
    if device is None:
        try:
            device_uuid = UUID(device_id)
            device = await service.get_device(device_uuid)
        except ValueError:
            device = None
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    task = run_compliance_eval.apply_async(args=[str(device.id), ["cis"]], queue="compliance")
    log.info("monitoring.force_poll", device_id=str(device_id), user_id=str(current_user.id))

    return {
        "device_id": str(device.id),
        "task_id": task.id,
        "status": "polling_queued",
        "message": "Device polling has been queued",
    }
