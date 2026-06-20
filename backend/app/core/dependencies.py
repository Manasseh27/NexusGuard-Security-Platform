"""
Platform Dependency Injection — async-safe service wiring.
All singletons are built once via ServiceContainer and injected via FastAPI Depends.
Tests override via app.dependency_overrides.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.container import get_container

log = structlog.get_logger(__name__)


# ── Service keys ───────────────────────────────────────────────────────────────

_K_REGISTRY     = "rule_registry"
_K_ORCHESTRATOR = "compliance_orchestrator"
_K_MONITOR      = "compliance_monitor"
_K_SIEM         = "siem_pipeline"
_K_COPILOT      = "copilot_service"
_K_EXEC_ENGINE  = "execution_engine"
_K_CONFIG_FETCH = "config_fetcher"
_K_CREDS_STORE  = "credentials_store"


# ── Synchronous accessors (safe after startup) ─────────────────────────────────

def get_rule_registry():
    svc = get_container().get(_K_REGISTRY)
    if svc is None:
        from app.domain.compliance.engine.compliance_engine import ComplianceRuleRegistry
        svc = ComplianceRuleRegistry()
        get_container().set(_K_REGISTRY, svc)
        log.info("deps.rule_registry.initialized")
    return svc


def get_compliance_orchestrator():
    svc = get_container().get(_K_ORCHESTRATOR)
    if svc is None:
        from app.domain.compliance.engine.compliance_engine import (
            ComplianceOrchestrator,
            OPAPolicyEvaluator,
        )
        from app.core.config import settings
        registry = get_rule_registry()
        opa = OPAPolicyEvaluator() if settings.ENABLE_OPA_POLICIES else None
        svc = ComplianceOrchestrator(registry=registry, opa_evaluator=opa, max_parallel_rules=10)
        get_container().set(_K_ORCHESTRATOR, svc)
        log.info("deps.orchestrator.initialized")
    return svc


def get_siem_pipeline():
    svc = get_container().get(_K_SIEM)
    if svc is None:
        from app.services.siem.siem_pipeline import build_siem_pipeline
        svc = build_siem_pipeline()
        get_container().set(_K_SIEM, svc)
        log.info("deps.siem_pipeline.initialized")
    return svc


def get_compliance_monitor():
    svc = get_container().get(_K_MONITOR)
    if svc is None:
        from app.services.compliance.continuous_monitor_refactored import ContinuousComplianceMonitor
        orchestrator = get_compliance_orchestrator()
        pipeline = get_siem_pipeline()
        redis = _get_redis_safe()
        _, config_fetcher, _ = _get_execution_engine()
        svc = ContinuousComplianceMonitor(
            orchestrator=orchestrator,
            config_fetcher=config_fetcher,
            siem_pipeline=pipeline,
            redis_client=redis,
        )
        get_container().set(_K_MONITOR, svc)
        log.info("deps.monitor.initialized")
    return svc


def get_copilot_service():
    svc = get_container().get(_K_COPILOT)
    if svc is None:
        from app.domain.ai.providers.copilot_service import (
            LLMProviderRegistry,
            AIResponseCache,
            SecurityCopilotService,
        )
        registry = LLMProviderRegistry()
        redis = _get_redis_safe()
        cache = AIResponseCache(redis_client=redis, ttl=3600)
        svc = SecurityCopilotService(registry=registry, cache=cache)
        get_container().set(_K_COPILOT, svc)
        log.info("deps.copilot.initialized")
    return svc


def _get_execution_engine():
    pipeline = get_container().get(_K_EXEC_ENGINE)
    if pipeline is None:
        from app.services.network.device_executor import build_execution_engine
        pipeline, config_fetcher, creds_store = build_execution_engine()
        get_container().set(_K_EXEC_ENGINE, pipeline)
        get_container().set(_K_CONFIG_FETCH, config_fetcher)
        get_container().set(_K_CREDS_STORE, creds_store)
        log.info("deps.execution_engine.initialized")
    return (
        pipeline,
        get_container().get(_K_CONFIG_FETCH),
        get_container().get(_K_CREDS_STORE),
    )


def _get_redis_safe():
    """Return Redis client or raise — never silently return None in production."""
    from app.infrastructure.cache.redis_client import get_redis
    from app.core.config import settings
    client = get_redis()
    if client is None and settings.ENVIRONMENT == "production":
        raise RuntimeError("Redis client is not initialized — cannot proceed in production")
    return client  # May be None in development/test — callers must handle


async def get_device_config(device_id: str) -> dict[str, Any] | None:
    """Fetch device config for background compliance tasks."""
    try:
        _, config_fetcher, creds_store = _get_execution_engine()
        creds = await creds_store.get_credentials(device_id)
        if creds:
            return await config_fetcher.fetch(device_id, "ios")
    except Exception as exc:
        log.error("deps.get_device_config.failed", device_id=device_id, error=str(exc))
    return None


# ── Lifecycle ──────────────────────────────────────────────────────────────────

async def startup_services() -> None:
    """Warm up all services during application lifespan startup."""
    log.info("deps.startup.beginning")
    get_rule_registry()
    get_compliance_orchestrator()
    pipeline = get_siem_pipeline()
    await pipeline.start()
    monitor = get_compliance_monitor()
    await monitor.start()
    log.info("deps.startup.complete")


async def shutdown_services() -> None:
    """Cleanly stop all background services during shutdown."""
    log.info("deps.shutdown.beginning")
    monitor = get_container().get(_K_MONITOR)
    if monitor:
        await monitor.stop()
    pipeline = get_container().get(_K_SIEM)
    if pipeline:
        await pipeline.stop()
    get_container().clear()
    log.info("deps.shutdown.complete")
