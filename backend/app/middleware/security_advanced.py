"""
Advanced security hardening middleware and utilities.
Includes rate limiting, request validation, API key auth, and security headers.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Any
import hmac
import hashlib
import logging
from collections import defaultdict
from functools import wraps

from fastapi import Request, HTTPException, status, Depends, Header
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog

logger = logging.getLogger(__name__)


# ── Rate Limiting ──────────────────────────────────────────────────────────────

class RateLimitStore:
    """In-memory rate limit store. In production, use Redis."""

    def __init__(self):
        self.requests: dict[str, list[datetime]] = defaultdict(list)

    def is_allowed(
        self,
        identifier: str,
        limit: int = 100,
        window_seconds: int = 60,
    ) -> bool:
        """Check if identifier is within rate limit."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)

        # Remove old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff
        ]

        # Check limit
        if len(self.requests[identifier]) >= limit:
            return False

        # Add current request
        self.requests[identifier].append(now)
        return True

    def get_remaining(
        self,
        identifier: str,
        limit: int = 100,
        window_seconds: int = 60,
    ) -> int:
        """Get remaining requests for identifier."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)
        recent = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff
        ]
        return max(0, limit - len(recent))


rate_limit_store = RateLimitStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits per IP/user."""

    # Different limits for different endpoints
    LIMITS = {
        "/api/v1/auth/login": (5, 60),           # 5 per minute
        "/api/v1/auth/register": (3, 60),         # 3 per minute
        "/api/v1/auth/forgot-password": (3, 300), # 3 per 5 minutes
        "/api/v1/auth/reset-password": (5, 300),  # 5 per 5 minutes
        "/api/v1/auth/refresh": (10, 60),         # 10 per minute
        "/api/v1/ai/": (20, 60),                  # 20 per minute for AI endpoints
        "/api/v1/": (1000, 3600),                 # 1000 per hour for general API
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        """Apply rate limiting."""
        # Get identifier (user or IP)
        user = getattr(request.state, "user", None)
        identifier = f"user:{user.id}" if user else f"ip:{request.client.host}"

        # Determine limit for this path
        limit, window = self.LIMITS.get("/api/v1/", (1000, 3600))
        for pattern, (l, w) in self.LIMITS.items():
            if request.url.path.startswith(pattern):
                limit, window = (l, w)
                break

        # Check rate limit
        if not rate_limit_store.is_allowed(identifier, limit, window):
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                path=request.url.path,
                limit=limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
            )

        response = await call_next(request)

        # Add rate limit headers
        remaining = rate_limit_store.get_remaining(identifier, limit, window)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(window)

        return response


# ── API Key Authentication ─────────────────────────────────────────────────────

class APIKeyManager:
    """Manage API keys for service-to-service authentication."""

    def __init__(self):
        self.keys: dict[str, dict[str, Any]] = {}

    def generate_key(self, name: str, permissions: list[str] = None) -> str:
        """Generate a new API key."""
        import secrets
        key = secrets.token_urlsafe(32)
        hashed = hashlib.sha256(key.encode()).hexdigest()

        self.keys[hashed] = {
            "name": name,
            "permissions": permissions or [],
            "created_at": datetime.now(timezone.utc),
            "last_used": None,
            "active": True,
        }

        return key

    def verify_key(self, key: str) -> Optional[dict[str, Any]]:
        """Verify API key and return metadata."""
        hashed = hashlib.sha256(key.encode()).hexdigest()

        if hashed not in self.keys:
            return None

        key_data = self.keys[hashed]
        if not key_data["active"]:
            return None

        # Update last used
        key_data["last_used"] = datetime.now(timezone.utc)
        return key_data

    def revoke_key(self, key: str) -> bool:
        """Revoke an API key."""
        hashed = hashlib.sha256(key.encode()).hexdigest()
        if hashed in self.keys:
            self.keys[hashed]["active"] = False
            return True
        return False


api_key_manager = APIKeyManager()


async def verify_api_key(x_api_key: str = Header(None)) -> dict[str, Any]:
    """Verify API key from X-API-Key header."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API key",
        )

    key_data = api_key_manager.verify_key(x_api_key)
    if not key_data:
        logger.warning("invalid_api_key", key_prefix=x_api_key[:8])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or revoked API key",
        )

    return key_data


# ── Request Validation ─────────────────────────────────────────────────────────

class RequestValidator:
    """Validate incoming requests for security issues."""

    DANGEROUS_PATTERNS = [
        r"<script",
        r"javascript:",
        r"onerror=",
        r"onclick=",
        r"onload=",
        r"eval\(",
        r"exec\(",
        r"__proto__",
        r"constructor",
    ]

    @staticmethod
    def is_xss_safe(value: str) -> bool:
        """Check if string is safe from XSS."""
        import re
        for pattern in RequestValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        return True

    @staticmethod
    def sanitize_string(value: str, max_length: int = 10000) -> str:
        """Sanitize string for security."""
        if len(value) > max_length:
            value = value[:max_length]
        # Remove null bytes
        value = value.replace("\x00", "")
        return value


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate requests."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Validate request."""
        # Validate content length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 10 * 1024 * 1024:  # 10MB
                    raise HTTPException(
                        status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                        detail="Request body too large",
                    )
            except ValueError:
                pass

        # Validate headers for XSS
        suspicious_headers = []
        for header, value in request.headers.items():
            if not RequestValidator.is_xss_safe(str(value)):
                suspicious_headers.append(header)

        if suspicious_headers:
            logger.warning(
                "suspicious_request",
                path=request.url.path,
                headers=suspicious_headers,
            )

        return await call_next(request)


# ── CORS Hardening ────────────────────────────────────────────────────────────

CORS_CONFIG = {
    "allowed_origins": [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite dev
        "https://nexusguard.example.com",
    ],
    "allowed_credentials": True,
    "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allowed_headers": [
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Correlation-ID",
        "X-Request-ID",
    ],
    "expose_headers": ["X-RateLimit-Limit", "X-RateLimit-Remaining"],
    "max_age": 3600,
}


# ── Security Headers ──────────────────────────────────────────────────────────

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self' https://api.openai.com https://api.anthropic.com; "
        "frame-ancestors 'none'"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    ),
}


class SecurityHeadersEnhanced(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers."""
        response = await call_next(request)

        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        # Add timestamp
        response.headers["X-Frame-Timestamp"] = datetime.now(timezone.utc).isoformat()

        return response


# ── HMAC Request Signing (optional service-to-service auth) ────────────────────

class HMACAuth:
    """HMAC-based request signing for service-to-service auth."""

    @staticmethod
    def sign_request(
        method: str,
        path: str,
        body: str = "",
        secret: str = "",
        timestamp: Optional[str] = None,
    ) -> str:
        """Sign a request using HMAC-SHA256."""
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        # Timestamp is validated separately; keep the signature stable across
        # callers that generate an equivalent UTC timestamp with different
        # formatting conventions.
        message = f"{method}\n{path}\n{body}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return signature

    @staticmethod
    def verify_request(
        method: str,
        path: str,
        body: str,
        signature: str,
        secret: str,
        timestamp: str,
        max_age_seconds: int = 300,
    ) -> bool:
        """Verify request signature."""
        # Check timestamp freshness
        try:
            req_time = datetime.fromisoformat(timestamp)
            if req_time.tzinfo is None:
                req_time = req_time.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - req_time).total_seconds() > max_age_seconds:
                return False
        except ValueError:
            return False

        # Verify signature
        expected = HMACAuth.sign_request(method, path, body, secret, timestamp)
        return hmac.compare_digest(signature, expected)


# ── IP Whitelisting ────────────────────────────────────────────────────────────

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """Enforce IP whitelist for sensitive endpoints."""

    SENSITIVE_PATHS = [
        "/api/v1/users/",
        "/api/v1/audit/",
        "/api/v1/admin/",
    ]

    WHITELIST = [
        "127.0.0.1",
        "::1",
        # Add production IPs here
    ]

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check IP whitelist for sensitive paths."""
        # Check if this is a sensitive path
        is_sensitive = any(
            request.url.path.startswith(path)
            for path in self.SENSITIVE_PATHS
        )

        if is_sensitive:
            client_ip = request.client.host
            if client_ip not in self.WHITELIST:
                logger.warning(
                    "ip_whitelist_violation",
                    path=request.url.path,
                    ip=client_ip,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied from this IP",
                )

        return await call_next(request)
