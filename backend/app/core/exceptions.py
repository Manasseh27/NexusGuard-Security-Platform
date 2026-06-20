"""
Domain exception hierarchy and FastAPI exception handlers.
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception."""
    status_code: int = 500
    error_code:  str = "internal_error"

    def __init__(self, message: str, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    status_code = 404
    error_code  = "not_found"


class UnauthorizedError(AppException):
    status_code = 401
    error_code  = "unauthorized"


class ForbiddenError(AppException):
    status_code = 403
    error_code  = "forbidden"


class ValidationError(AppException):
    status_code = 422
    error_code  = "validation_error"


class ConflictError(AppException):
    status_code = 409
    error_code  = "conflict"


class DeviceConnectionError(AppException):
    status_code = 502
    error_code  = "device_connection_error"


class ComplianceEngineError(AppException):
    status_code = 500
    error_code  = "compliance_engine_error"


class AIProviderError(AppException):
    status_code = 503
    error_code  = "ai_provider_error"


class SIEMDeliveryError(AppException):
    status_code = 502
    error_code  = "siem_delivery_error"


# ── Exception handlers ─────────────────────────────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error":      exc.error_code,
            "message":    exc.message,
            "details":    exc.details,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error":   "validation_error",
            "message": "Request validation failed",
            "details": exc.errors(),
            "request_id": getattr(request.state, "request_id", None),
        },
    )
