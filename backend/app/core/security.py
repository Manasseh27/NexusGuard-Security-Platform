"""
Security utilities: JWT token handling, RBAC enforcement, permission decorators.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any
from uuid import UUID, uuid4

import bcrypt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

log = structlog.get_logger(__name__)
bearer_scheme = HTTPBearer()

# bcrypt hard limit — passwords longer than this are silently truncated by the
# algorithm, which is a security risk. We reject them explicitly instead.
_BCRYPT_MAX_BYTES = 72


# ── Permission definitions ─────────────────────────────────────────────────────

PERMISSIONS: dict[str, list[str]] = {
    "viewer": [
        "compliance:read", "devices:read", "audit:read",
        "monitoring:read", "threats:read", "reports:read",
        "siem:read", "incidents:read", "notifications:read",
    ],
    "auditor": [
        "compliance:read", "devices:read", "audit:read",
        "monitoring:read", "reports:read", "siem:read",
        "threats:read", "incidents:read", "notifications:read",
    ],
    "security_analyst": [
        "compliance:read", "compliance:evaluate", "compliance:acknowledge",
        "devices:read", "audit:read", "audit:execute",
        "monitoring:read", "threats:read", "reports:read",
        "siem:read", "siem:write",
        "incidents:read", "incidents:write", "incidents:assign",
        "notifications:read", "notifications:write",
        "ai:chat", "ai:explain", "ai:analyze", "ai:summarize",
    ],
    "soc_analyst": [
        "compliance:read", "compliance:evaluate", "compliance:acknowledge",
        "compliance:exception:create",
        "devices:read", "devices:write", "devices:execute",
        "audit:read", "audit:execute",
        "monitoring:read", "monitoring:write",
        "threats:read", "threats:write",
        "reports:read", "reports:write",
        "incidents:read", "incidents:write", "incidents:assign",
        "notifications:read", "notifications:write",
        "ai:chat", "ai:explain", "ai:analyze", "ai:remediation", "ai:summarize",
        "siem:read", "siem:write",
    ],
    "admin": [
        "*",
    ],
    "super_admin": [
        "*",
    ],
}

ROLE_ALIASES: dict[str, str] = {
    "engineer": "soc_analyst",
    "analyst": "security_analyst",
    "secops_lead": "soc_analyst",
    "admin": "admin",
    "super_admin": "super_admin",
    "security_analyst": "security_analyst",
    "soc_analyst": "soc_analyst",
    "auditor": "auditor",
    "viewer": "viewer",
}

PASSWORD_POLICY = {
    "min_length": 12,
    "requires_upper": True,
    "requires_lower": True,
    "requires_digit": True,
    "requires_special": True,
}


class TokenData(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    permissions: list[str]
    tenant_id: str = "default"
    session_id: str | None = None
    token_id: str | None = None
    expires_at: datetime | None = None


class CurrentUser(BaseModel):
    id: UUID
    username: str
    email: str
    role: str
    permissions: list[str]
    tenant_id: str = "default"

    def has_permission(self, permission: str) -> bool:
        if "*" in self.permissions:
            return True
        return permission in self.permissions


def canonical_role(role: str) -> str:
    """Normalize legacy role names to the canonical permission model."""
    return ROLE_ALIASES.get(role, role)


def permissions_for_role(role: str) -> list[str]:
    """Resolve permissions for a role, including legacy aliases."""
    return PERMISSIONS.get(canonical_role(role), PERMISSIONS["viewer"])


def validate_password_policy(password: str) -> None:
    """Enforce the platform password policy."""
    if len(password) < PASSWORD_POLICY["min_length"]:
        raise ValueError("Password must be at least 12 characters long")
    if PASSWORD_POLICY["requires_upper"] and not any(ch.isupper() for ch in password):
        raise ValueError("Password must include at least one uppercase letter")
    if PASSWORD_POLICY["requires_lower"] and not any(ch.islower() for ch in password):
        raise ValueError("Password must include at least one lowercase letter")
    if PASSWORD_POLICY["requires_digit"] and not any(ch.isdigit() for ch in password):
        raise ValueError("Password must include at least one number")
    if PASSWORD_POLICY["requires_special"] and not any(not ch.isalnum() for ch in password):
        raise ValueError("Password must include at least one special character")


# ── Token creation ─────────────────────────────────────────────────────────────

def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.setdefault("jti", str(uuid4()))
    payload.update({
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "iss": settings.jwt.ISSUER,
        "aud": settings.jwt.AUDIENCE,
        "type": "access",
    })
    return jwt.encode(payload, settings.jwt.SECRET_KEY, algorithm=settings.jwt.ALGORITHM)


def create_refresh_token(data: dict[str, Any], expires_in_days: int | None = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=expires_in_days or settings.jwt.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload.setdefault("jti", str(uuid4()))
    payload.update({
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "iss": settings.jwt.ISSUER,
        "aud": settings.jwt.AUDIENCE,
        "type": "refresh",
    })
    return jwt.encode(payload, settings.jwt.SECRET_KEY, algorithm=settings.jwt.ALGORITHM)


# ── Token verification ─────────────────────────────────────────────────────────

def decode_token(token: str, token_type: str | None = None) -> TokenData:
    try:
        payload = jwt.decode(
            token,
            settings.jwt.SECRET_KEY,
            algorithms=[settings.jwt.ALGORITHM],
            audience=settings.jwt.AUDIENCE,
            issuer=settings.jwt.ISSUER,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if token_type is not None and payload.get("type") != token_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid {token_type} token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = canonical_role(payload.get("role", "viewer"))
    permissions = permissions_for_role(role)

    expires_at = payload.get("exp")
    if isinstance(expires_at, (int, float)):
        expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)

    return TokenData(
        user_id=payload.get("sub", ""),
        username=payload.get("username", ""),
        email=payload.get("email", ""),
        role=role,
        permissions=permissions,
        tenant_id=payload.get("tenant_id", "default"),
        session_id=payload.get("sid"),
        token_id=payload.get("jti"),
        expires_at=expires_at,
    )


async def is_token_revoked(token: str) -> bool:
    """Check whether a JWT has been revoked via Redis blacklist."""
    from app.infrastructure.cache.redis_client import get_redis

    redis_client = get_redis()
    if redis_client is None:
        return False

    try:
        token_data = decode_token(token)
    except HTTPException:
        return True

    if not token_data.token_id:
        return False
    return bool(await redis_client.exists(f"jwt:revoked:{token_data.token_id}"))


async def revoke_token(token: str, token_type: str | None = None) -> None:
    """Revoke a JWT by storing its jti in Redis until it expires."""
    from app.infrastructure.cache.redis_client import get_redis

    redis_client = get_redis()
    if redis_client is None:
        return

    token_data = decode_token(token, token_type=token_type)
    if not token_data.token_id or token_data.expires_at is None:
        return

    ttl = int((token_data.expires_at - datetime.now(timezone.utc)).total_seconds())
    if ttl <= 0:
        return

    await redis_client.setex(f"jwt:revoked:{token_data.token_id}", ttl, token_type or "token")


async def cache_session(token_id: str, user_id: str, ttl_seconds: int, metadata: dict[str, Any] | None = None) -> None:
    """Track an active auth session in Redis."""
    from app.infrastructure.cache.redis_client import get_redis

    redis_client = get_redis()
    if redis_client is None or ttl_seconds <= 0:
        return

    payload = {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }
    await redis_client.setex(f"auth:session:{token_id}", ttl_seconds, json.dumps(payload))


async def record_login_attempt(username: str, success: bool, *, max_attempts: int = 5, lockout_seconds: int = 900) -> int:
    """Record a login attempt and return the current failure count."""
    from app.infrastructure.cache.redis_client import get_redis

    redis_client = get_redis()
    if redis_client is None:
        return 0

    key = f"auth:login_attempts:{username.lower()}"
    lock_key = f"auth:locked:{username.lower()}"

    if success:
        await redis_client.delete(key)
        await redis_client.delete(lock_key)
        return 0

    attempts = await redis_client.incr(key)
    if attempts == 1:
        await redis_client.expire(key, lockout_seconds)
    if attempts >= max_attempts:
        await redis_client.setex(lock_key, lockout_seconds, "locked")
    return attempts


async def is_account_locked(username: str) -> bool:
    """Check whether an account is currently locked."""
    from app.infrastructure.cache.redis_client import get_redis

    redis_client = get_redis()
    if redis_client is None:
        return False
    return bool(await redis_client.exists(f"auth:locked:{username.lower()}"))


async def clear_login_attempts(username: str) -> None:
    """Reset login failure state after a successful login."""
    from app.infrastructure.cache.redis_client import get_redis

    redis_client = get_redis()
    if redis_client is None:
        return
    await redis_client.delete(f"auth:login_attempts:{username.lower()}")
    await redis_client.delete(f"auth:locked:{username.lower()}")


# ── FastAPI dependencies ───────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    if await is_token_revoked(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_token(credentials.credentials)
    try:
        user_id = UUID(token_data.user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID in token")

    user = CurrentUser(
        id=          user_id,
        username=    token_data.username,
        email=       token_data.email,
        role=        token_data.role,
        permissions= token_data.permissions,
        tenant_id=   token_data.tenant_id,
    )

    structlog.contextvars.bind_contextvars(
        user_id=token_data.user_id,
        username=token_data.username,
        role=token_data.role,
    )

    return user


def require_permission(permission: str):
    """Factory: returns a FastAPI dependency that enforces a specific permission."""
    async def _check(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not current_user.has_permission(permission):
            log.warning(
                "security.permission.denied",
                user=current_user.username,
                required=permission,
                role=current_user.role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required. Your role: {current_user.role}",
            )
        return current_user
    return _check


# ── Password utilities ─────────────────────────────────────────────────────────

def _assert_password_length(password: str) -> None:
    """Raise ValueError before bcrypt sees an oversized input."""
    if len(password.encode()) > _BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password exceeds bcrypt's 72-byte limit "
            f"({len(password.encode())} bytes). "
            "Do not hash SECRET_KEY, JWT secrets, or API tokens with bcrypt."
        )


def hash_password(password: str) -> str:
    """Hash a user password with bcrypt. Input must be a real password ≤72 bytes."""
    _assert_password_length(password)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    if len(plain.encode()) > _BCRYPT_MAX_BYTES:
        return False
    return bcrypt.checkpw(plain.encode(), hashed.encode())
