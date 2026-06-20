"""
Async PostgreSQL session management.
Uses SQLAlchemy 2.0 async engine with connection pool tuning.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.infrastructure.database.base import Base

log = structlog.get_logger(__name__)


# ── Engine (created once at module load) ───────────────────────────────────────

engine: AsyncEngine = create_async_engine(
    settings.database.async_url,
    pool_size=settings.database.POOL_SIZE,
    max_overflow=settings.database.MAX_OVERFLOW,
    pool_timeout=settings.database.POOL_TIMEOUT,
    pool_recycle=settings.database.POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.database.ECHO,
    connect_args={
        "server_settings": {
            "application_name": settings.SERVICE_NAME,
            "jit": "off",
        },
        "command_timeout": 30,
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Import all models to register them with SQLAlchemy
# (Must be after Base and engine definition)
from app.infrastructure.database.models import (  # noqa: E402, F401
    User,
    Device,
    DeviceCredentials,
    DeviceMonitoringState,
    ComplianceScore,
    ComplianceResult,
    DriftEvent,
    RemediationJob,
    AuditLog,
    SIEMEvent,
    ComplianceException,
    Incident,
    IncidentComment,
    IncidentTimeline,
    Notification,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables on startup (development). Production uses Alembic."""
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("database.tables.created")

        if settings.ENABLE_DEMO_DATA:
            async with AsyncSessionLocal() as session:
                from app.services.user_service import UserService

                user_service = UserService(session)
                demo_users = await user_service.ensure_demo_users()
                if demo_users:
                    await session.commit()
                    log.info("database.demo_users.created", count=len(demo_users))
        else:
            log.info("database.demo_users.skipped", reason="ENABLE_DEMO_DATA is false")

    log.info("database.initialized", url=settings.database.HOST)


async def check_db_health() -> bool:
    """Readiness probe: verify DB connection is alive."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.error("database.health_check.failed", error=str(exc))
        return False
