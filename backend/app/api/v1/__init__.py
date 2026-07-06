"""
API v1 Router — Master aggregator for all platform endpoints.
"""
from fastapi import APIRouter

from app.api.v1.routers import (
    auth,
    devices,
    compliance,
    audit,
    ai_copilot,
    siem,
    threats,
    reports,
    health_advanced,
    users,
    monitoring,
    incidents,
    notifications,
    dashboard,
)

router = APIRouter()

router.include_router(auth.router,           prefix="/auth",       tags=["Authentication"])
router.include_router(users.router,          prefix="/users",      tags=["Users & RBAC"])
router.include_router(devices.router,        prefix="/devices",    tags=["Devices"])
router.include_router(compliance.router,     prefix="/compliance", tags=["Compliance"])
router.include_router(audit.router,          prefix="/audit",      tags=["Audit"])
router.include_router(ai_copilot.router,     prefix="/ai",         tags=["AI Copilot"])
router.include_router(siem.router,           prefix="/siem",       tags=["SIEM"])
router.include_router(threats.router,        prefix="/threats",    tags=["Threat Intelligence"])
router.include_router(reports.router,        prefix="/reports",    tags=["Reports"])
router.include_router(monitoring.router,     prefix="/monitoring", tags=["Continuous Monitoring"])
router.include_router(incidents.router,      prefix="/incidents",  tags=["Incidents"])
router.include_router(notifications.router,  prefix="/notifications", tags=["Notifications"])
router.include_router(health_advanced.router,prefix="/health",     tags=["Health"])
router.include_router(dashboard.router,      prefix="/dashboard",  tags=["Dashboard"])
