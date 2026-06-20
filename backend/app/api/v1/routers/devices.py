"""Devices router — full CRUD with database persistence."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import DeviceType
from app.services.device_service import DeviceService

router = APIRouter()


class DeviceCreate(BaseModel):
    device_id: str | None = None
    hostname: str = Field(..., min_length=1, max_length=256)
    ip_address: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    device_type: str = "generic"
    site: str = Field(default="", max_length=128)
    tags: list[str] = Field(default_factory=list, max_length=50)
    credentials_ref: str | None = None


class DeviceUpdate(BaseModel):
    hostname: str | None = None
    site: str | None = None
    tags: list[str] | None = None
    is_enabled: bool | None = None


class DeviceResponse(BaseModel):
    id: str
    device_id: str
    hostname: str
    ip_address: str
    device_type: str
    site: str
    tags: list[str]
    is_enabled: bool
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    site: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
    limit: int = Query(default=25, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("devices:read")),
):
    """List all devices with filtering."""
    service = DeviceService(db)
    tenant_id = current_user.tenant_id

    if device_type:
        devices = await service.list_devices_by_type(tenant_id, device_type, limit, offset)
    elif site:
        devices = await service.list_devices_by_site(tenant_id, site, limit, offset)
    else:
        devices = await service.list_devices_by_tenant(tenant_id, limit, offset)

    return [
        DeviceResponse(
            id=str(d.id),
            device_id=d.device_id,
            hostname=d.hostname,
            ip_address=d.ip_address,
            device_type=d.device_type.value,
            site=d.site,
            tags=d.tags,
            is_enabled=d.is_enabled,
            created_at=d.created_at.isoformat(),
        )
        for d in devices
    ]


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("devices:write")),
):
    """Create a new device."""
    service = DeviceService(db)
    try:
        device = await service.create_device(
            device_id=payload.device_id,
            hostname=payload.hostname,
            ip_address=payload.ip_address,
            device_type=DeviceType(payload.device_type),
            site=payload.site,
            tags=payload.tags,
            tenant_id=current_user.tenant_id,
        )
        await db.commit()
        return DeviceResponse(
            id=str(device.id),
            device_id=device.device_id,
            hostname=device.hostname,
            ip_address=device.ip_address,
            device_type=device.device_type.value,
            site=device.site,
            tags=device.tags,
            is_enabled=device.is_enabled,
            created_at=device.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("devices:read")),
):
    """Get a specific device."""
    service = DeviceService(db)
    device = await service.get_device(device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return DeviceResponse(
        id=str(device.id),
        device_id=device.device_id,
        hostname=device.hostname,
        ip_address=device.ip_address,
        device_type=device.device_type.value,
        site=device.site,
        tags=device.tags,
        is_enabled=device.is_enabled,
        created_at=device.created_at.isoformat(),
    )


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("devices:write")),
):
    """Update device properties."""
    service = DeviceService(db)
    device = await service.get_device(device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    update_data = payload.dict(exclude_unset=True)
    updated = await service.update_device(device_id, **update_data)
    await db.commit()

    return DeviceResponse(
        id=str(updated.id),
        device_id=updated.device_id,
        hostname=updated.hostname,
        ip_address=updated.ip_address,
        device_type=updated.device_type.value,
        site=updated.site,
        tags=updated.tags,
        is_enabled=updated.is_enabled,
        created_at=updated.created_at.isoformat(),
    )


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("devices:write")),
):
    """Delete a device."""
    service = DeviceService(db)
    device = await service.get_device(device_id)
    if not device or device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    await service.delete_device(device_id)
    await db.commit()
    return None

