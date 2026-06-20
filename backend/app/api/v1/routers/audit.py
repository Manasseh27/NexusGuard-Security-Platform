"""
Audit router — immutable audit log access.
"""

from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select

from app.core.security import get_current_user, require_permission
from app.infrastructure.database.models import AuditLog, User
from app.infrastructure.database.session import get_db
from app.infrastructure.database.repositories import AuditLogRepository

import structlog

log = structlog.get_logger(__name__)
router = APIRouter()


class AuditEntryResponse(BaseModel):
    audit_id: str
    timestamp: str
    user_id: str
    username: str
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    details: dict


@router.get("", response_model=list[AuditEntryResponse])
async def list_audit_logs(
    action: str | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("audit:read")),
) -> list[AuditEntryResponse]:
    """List audit log entries."""
    stmt = (
        select(AuditLog, User.username)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(AuditLog.tenant_id == current_user.tenant_id)
        .order_by(desc(AuditLog.timestamp))
        .limit(limit)
        .offset(offset)
    )
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)

    rows = (await db.execute(stmt)).all()
    
    return [
        AuditEntryResponse(
            audit_id=str(entry.id),
            timestamp=entry.timestamp.isoformat() if entry.timestamp else datetime.now().isoformat(),
            user_id=str(entry.user_id) if entry.user_id else "system",
            username=username or "system",
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=str(entry.resource_id) if entry.resource_id else None,
            outcome=entry.status,
            details=entry.details or {},
        )
        for entry, username in rows
    ]


@router.get("/{audit_id}", response_model=AuditEntryResponse)
async def get_audit_entry(
    audit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("audit:read")),
) -> AuditEntryResponse:
    """Get a specific audit log entry."""
    audit_repo = AuditLogRepository(db)
    entry = await audit_repo.get_by_id(audit_id)
    
    if not entry or entry.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit entry not found",
        )
    
    return AuditEntryResponse(
        audit_id=str(entry.id),
        timestamp=entry.timestamp.isoformat() if entry.timestamp else datetime.now().isoformat(),
        user_id=str(entry.user_id) if entry.user_id else "system",
        username="system",
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=str(entry.resource_id) if entry.resource_id else None,
        outcome=entry.status,
        details=entry.details or {},
    )


@router.get("/actions/{action}/count")
async def audit_action_count(
    action: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("audit:read")),
) -> dict:
    """Get count of a specific action in audit log."""
    entries = await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == current_user.tenant_id, AuditLog.action == action)
        .order_by(desc(AuditLog.timestamp))
        .limit(10000)
    )
    rows = entries.scalars().all()
    
    return {
        "action": action,
        "count": len(rows),
        "last_occurrence": rows[0].timestamp.isoformat() if rows else None,
    }
