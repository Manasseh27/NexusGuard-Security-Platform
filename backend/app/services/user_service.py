"""
User and Authentication Service
Handles user management, authentication, and role-based access control.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.infrastructure.database.models import User, UserRole
from app.infrastructure.database.repositories import UserRepository

log = structlog.get_logger(__name__)


class UserService:
    """User account management and authentication."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = UserRepository(db)

    async def authenticate(self, username: str, password: str) -> User | None:
        """Authenticate user by username and password."""
        user = await self.repository.get_by_username(username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            log.warning("auth.authentication.failed", username=username)
            return None
        # Update last login
        user.last_login = datetime.now(timezone.utc)
        await self.db.flush()
        log.info("auth.authentication.success", user_id=str(user.id), username=username)
        return user

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.VIEWER,
        tenant_id: str = "default",
    ) -> User:
        """Create a new user."""
        if await self.repository.get_by_username(username):
            raise ValueError(f"User '{username}' already exists")
        if await self.repository.get_by_email(email):
            raise ValueError(f"Email '{email}' already exists")

        user = await self.repository.create(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
            tenant_id=tenant_id,
            is_active=True,
            is_service_account=False,
        )
        log.info("user.created", user_id=str(user.id), username=username, role=role)
        return user

    async def get_user(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        return await self.repository.get_by_id(user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        return await self.repository.get_by_username(username)

    async def update_user_role(self, user_id: UUID, new_role: UserRole) -> User | None:
        """Update user role."""
        user = await self.repository.update(user_id, role=new_role)
        if user:
            log.info("user.role.updated", user_id=str(user_id), new_role=new_role)
        return user

    async def deactivate_user(self, user_id: UUID) -> User | None:
        """Deactivate user account."""
        user = await self.repository.update(user_id, is_active=False)
        if user:
            log.info("user.deactivated", user_id=str(user_id))
        return user

    async def change_password(self, user_id: UUID, new_password: str) -> bool:
        """Change user password."""
        user = await self.repository.get_by_id(user_id)
        if not user:
            return False
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        log.info("user.password.changed", user_id=str(user_id))
        return True

    async def list_users_by_tenant(self, tenant_id: str, limit: int = 100, offset: int = 0) -> list[User]:
        """List users in a tenant."""
        return await self.repository.list_by_tenant(tenant_id, limit, offset)

    async def ensure_demo_users(self, tenant_id: str = "default") -> list[User]:
        """Create demo users if they don't exist. Used for initial setup."""
        demo_users = [
            ("admin", "admin@example.com", "admin123", UserRole.ADMIN),
            ("engineer", "engineer@example.com", "engineer123", UserRole.ENGINEER),
            ("analyst", "analyst@example.com", "analyst123", UserRole.ANALYST),
            ("viewer", "viewer@example.com", "viewer123", UserRole.VIEWER),
        ]
        created = []
        for username, email, password, role in demo_users:
            existing = await self.repository.get_by_username(username)
            if existing:
                continue
            user = await self.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
                tenant_id=tenant_id,
            )
            created.append(user)
        return created
