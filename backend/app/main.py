"""
Cisco Security Platform - Enterprise FastAPI Application
Principal entry point with full middleware stack, observability, and security hardening
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
)
from app.core.metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    ACTIVE_CONNECTIONS,
)
from app.core.security_config import validate_security_startup
from app.infrastructure.database.session import engine, init_db
from app.infrastructure.cache.redis_client import init_redis, close_redis
from app.infrastructure.messaging.broker import init_broker, close_broker
from app.middleware.security_headers import (
    AuditMiddleware,
    SecurityHeadersMiddleware,
)
from app.middleware.security_advanced import (
    RateLimitMiddleware,
    RequestValidationMiddleware,
    SecurityHeadersEnhanced,
    IPWhitelistMiddleware,
)

log = structlog.get_logger(__name__)


def configure_telemetry() -> None:
    """Configure OpenTelemetry distributed tracing."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:
        log.warning("telemetry.disabled", error=str(exc))
        return

    resource = Resource.create({
        "service.name": settings.SERVICE_NAME,
        "service.version": settings.VERSION,
        "deployment.environment": settings.ENVIRONMENT,
    })
    provider = TracerProvider(resource=resource)
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        try:
            exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception as exc:
            log.warning("telemetry.exporter_disabled", error=str(exc))
    trace.set_tracer_provider(provider)
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except Exception as exc:
        log.warning("telemetry.sqlalchemy_instrumentation_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup → yield → shutdown."""
    log.info("platform.startup", version=settings.VERSION, env=settings.ENVIRONMENT)

    # Validate security configuration
    try:
        validate_security_startup()
    except Exception as e:
        log.critical("security_validation_failed", error=str(e))
        raise

    await init_db()
    await init_redis()
    await init_broker()
    configure_telemetry()

    from app.core.dependencies import startup_services
    await startup_services()

    log.info("platform.ready", service=settings.SERVICE_NAME)
    yield

    log.info("platform.shutdown")
    from app.core.dependencies import shutdown_services
    await shutdown_services()
    await close_redis()
    await close_broker()


def create_application() -> FastAPI:
    """Factory: build the fully configured FastAPI application."""
    app = FastAPI(
        title="NexusGuard Security Platform",
        description="Enterprise-grade cybersecurity compliance and automation platform",
        version=settings.VERSION,
        docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # ── Security middleware (order matters — outermost first) ──────────────────
    app.add_middleware(SecurityHeadersEnhanced)
    app.add_middleware(IPWhitelistMiddleware)
    app.add_middleware(RequestValidationMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Correlation-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        same_site="strict",
        https_only=settings.ENVIRONMENT == "production",
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # ── Request correlation & metrics middleware ───────────────────────────────
    @app.middleware("http")
    async def request_telemetry(request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        correlation_id = request.headers.get("X-Correlation-ID", request_id)
        response: Response | None = None

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        ACTIVE_CONNECTIONS.inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            log.error("request.unhandled_error", error=str(exc))
            raise
        finally:
            duration = time.perf_counter() - start
            ACTIVE_CONNECTIONS.dec()
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                path=request.url.path,
                status=getattr(response, "status_code", 500),
            ).inc()
            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                path=request.url.path,
            ).observe(duration)

            structlog.contextvars.clear_contextvars()

        if response is not None:
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            return response

        raise RuntimeError("request telemetry middleware did not receive a response")

    # ── Exception handlers ─────────────────────────────────────────────────────
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(api_v1_router, prefix="/api/v1")

    # ── Prometheus metrics endpoint ────────────────────────────────────────────
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # ── Health endpoints ───────────────────────────────────────────────────────
    @app.get("/health/live", tags=["health"], include_in_schema=False)
    async def liveness() -> dict:
        return {"status": "alive", "service": settings.SERVICE_NAME}

    @app.get("/health/ready", tags=["health"], include_in_schema=False)
    async def readiness() -> dict:
        from app.infrastructure.database.session import check_db_health
        from app.infrastructure.cache.redis_client import check_redis_health
        checks = {
            "database": await check_db_health(),
            "cache": await check_redis_health(),
        }
        healthy = all(checks.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ready" if healthy else "degraded", "checks": checks},
        )

    @app.get("/health/detailed", tags=["health"], include_in_schema=False)
    async def detailed_health() -> dict:
        from app.infrastructure.database.session import check_db_health
        from app.infrastructure.cache.redis_client import check_redis_health
        from app.infrastructure.messaging.events import get_event_bus
        from app.core.dependencies import get_container

        checks = {
            "database": await check_db_health(),
            "cache": await check_redis_health(),
        }

        siem = get_container().get("siem_pipeline")
        siem_health = await siem.health_status() if siem else {}

        monitor = get_container().get("compliance_monitor")
        fleet = monitor.get_fleet_summary() if monitor else {}

        event_bus_stats = get_event_bus().get_stats()

        return JSONResponse(
            status_code=200 if all(checks.values()) else 503,
            content={
                "status": "ready" if all(checks.values()) else "degraded",
                "checks": checks,
                "siem": siem_health,
                "fleet": fleet,
                "event_bus": event_bus_stats,
            },
        )

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        log.warning("telemetry.fastapi_instrumentation_failed", error=str(exc))
    return app


app = create_application()
