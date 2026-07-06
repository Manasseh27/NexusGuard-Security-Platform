"""
Users & RBAC router.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_permission
from app.infrastructure.database.models import UserRole
from app.infrastructure.database.session import get_db
from app.services.user_service import UserService

import structlog

log = structlog.get_logger(__name__)
router = APIRouter()


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    tenant_id: str
    last_login: str | None


class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole


class UpdateUserRequest(BaseModel):
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None


@router.get("", response_model=list[UserResponse])
async def list_users(
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("users:read")),
) -> list[UserResponse]:
    """List all users in the tenant."""
    user_service = UserService(db)
    users = await user_service.list_users_by_tenant(current_user.tenant_id, limit, offset)
    
    return [
        UserResponse(
            id=str(u.id),
            username=u.username,
            email=u.email,
            role=u.role.value,
            is_active=u.is_active,
            tenant_id=u.tenant_id,
            last_login=u.last_login.isoformat() if u.last_login else None,
        )
        for u in users
    ]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("users:write")),
) -> UserResponse:
    """Create a new user in the tenant."""
    user_service = UserService(db)
    
    # Check if user already exists
    existing = await user_service.get_user_by_username(request.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    
    user = await user_service.create_user(
        username=request.username,
        email=request.email,
        password=request.password,
        role=request.role,
        tenant_id=current_user.tenant_id,
    )
    await db.commit()
    
    log.info(
        "users.created",
        username=request.username,
        role=request.role.value,
        user_id=str(current_user.id),
    )
    
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        tenant_id=user.tenant_id,
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("users:read")),
) -> UserResponse:
    """Get a specific user."""
    user_service = UserService(db)
    user = await user_service.get_user(user_id)
    
    if not user or user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        tenant_id=user.tenant_id,
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("users:write")),
) -> UserResponse:
    """Update a user."""
    user_service = UserService(db)
    user = await user_service.get_user(user_id)
    
    if not user or user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Update fields if provided
    if request.email:
        user.email = request.email
    if request.role:
        await user_service.update_user_role(user_id, request.role)
    if request.is_active is not None:
        user.is_active = request.is_active
    
    await db.commit()
    
    log.info(
        "users.updated",
        user_id=str(user_id),
        updated_by=str(current_user.id),
    )
    
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        tenant_id=user.tenant_id,
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("users:write")),
):
    """Delete a user (soft delete - sets is_active=False)."""
    user_service = UserService(db)
    user = await user_service.get_user(user_id)
    
    if not user or user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    await user_service.deactivate_user(user_id)
    await db.commit()
    
    log.info(
        "users.deactivated",
        user_id=str(user_id),
        deactivated_by=str(current_user.id),
    )
