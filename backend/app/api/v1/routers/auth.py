"""
Auth router — registration, login, token refresh, logout, recovery, verification, sessions.
Uses database-backed user authentication with bcrypt password hashing and Redis-backed session state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

from app.core.security import (
    bearer_scheme,
    cache_session,
    canonical_role,
    clear_login_attempts,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    is_account_locked,
    permissions_for_role,
    record_login_attempt,
    revoke_token,
    validate_password_policy,
)
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.database.models import UserRole
from app.infrastructure.database.session import get_db
from app.services.user_service import UserService

log = structlog.get_logger(__name__)
router = APIRouter()

LOCKOUT_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
RESET_TOKEN_SECONDS = 60 * 60
VERIFICATION_TOKEN_SECONDS = 24 * 60 * 60


class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.VIEWER
    tenant_id: str = Field(default="default", max_length=64)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=12, max_length=128)


class VerifyEmailRequest(BaseModel):
    verification_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    username: str
    created_at: str
    last_seen_at: str | None = None
    remember_me: bool = False
    active: bool = True


class GenericMessageResponse(BaseModel):
    message: str
    token: str | None = None


def _session_key(session_id: str) -> str:
    return f"auth:session:{session_id}"


async def _build_tokens(
    user,
    *,
    remember_me: bool = False,
    session_id: str | None = None,
) -> TokenResponse:
    session_id = session_id or str(uuid4())
    refresh_days = 30 if remember_me else None

    access_token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": canonical_role(user.role.value),
        "permissions": permissions_for_role(user.role.value),
        "tenant_id": user.tenant_id,
        "sid": session_id,
    })
    refresh_token = create_refresh_token({
        "sub": str(user.id),
        "username": user.username,
        "tenant_id": user.tenant_id,
        "sid": session_id,
    }, expires_in_days=refresh_days)

    access_data = decode_token(access_token, token_type="access")
    refresh_data = decode_token(refresh_token, token_type="refresh")
    ttl_seconds = int((refresh_data.expires_at - datetime.now(timezone.utc)).total_seconds()) if refresh_data.expires_at else 0
    await cache_session(
        session_id,
        str(user.id),
        ttl_seconds,
        metadata={
            "username": user.username,
            "access_jti": access_data.token_id,
            "refresh_jti": refresh_data.token_id,
            "remember_me": remember_me,
            "tenant_id": user.tenant_id,
        },
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
    )


async def _store_token_record(key: str, payload: dict[str, str], ttl_seconds: int) -> None:
    redis_client = get_redis()
    if redis_client is None or ttl_seconds <= 0:
        return
    await redis_client.setex(key, ttl_seconds, json.dumps(payload))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db=Depends(get_db)) -> TokenResponse:
    """Register a new user and issue initial tokens."""
    validate_password_policy(request.password)

    user_service = UserService(db)
    if await user_service.get_user_by_username(request.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    if await user_service.repository.get_by_email(request.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    user = await user_service.create_user(
        username=request.username,
        email=request.email,
        password=request.password,
        role=request.role,
        tenant_id=request.tenant_id,
    )

    verification_token = str(uuid4())
    await _store_token_record(
        f"auth:verify:{verification_token}",
        {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "tenant_id": user.tenant_id,
        },
        VERIFICATION_TOKEN_SECONDS,
    )

    log.info("auth.register.success", user_id=str(user.id), username=user.username)
    return await _build_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db=Depends(get_db)) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    if await is_account_locked(request.username):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account temporarily locked due to failed login attempts")

    user_service = UserService(db)
    user = await user_service.authenticate(request.username, request.password)
    if not user:
        attempts = await record_login_attempt(request.username, success=False, max_attempts=LOCKOUT_ATTEMPTS, lockout_seconds=LOCKOUT_SECONDS)
        log.warning("auth.login.failed", username=request.username, attempts=attempts)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await clear_login_attempts(request.username)
    tokens = await _build_tokens(user, remember_me=request.remember_me)

    log.info("auth.login.success", user_id=str(user.id), username=user.username, remember_me=request.remember_me)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, db=Depends(get_db)) -> TokenResponse:
    """Refresh access token using refresh token."""
    try:
        if await is_account_locked(decode_token(request.refresh_token, token_type="refresh").username):
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account temporarily locked")

        refresh_data = decode_token(request.refresh_token, token_type="refresh")
        if not refresh_data.session_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session context")

        redis_client = get_redis()
        if redis_client is None or not await redis_client.exists(_session_key(refresh_data.session_id)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("auth.refresh.failed", error=str(exc))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_service = UserService(db)
    user = await user_service.get_user_by_username(refresh_data.username)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    tokens = await _build_tokens(user, session_id=refresh_data.session_id)
    await revoke_token(request.refresh_token, token_type="refresh")

    log.info("auth.refresh.success", user_id=str(user.id), session_id=refresh_data.session_id)
    return tokens


@router.get("/me")
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Get current authenticated user info."""
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "permissions": current_user.permissions,
        "tenant_id": current_user.tenant_id,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Logout and revoke the current session."""
    token_data = decode_token(credentials.credentials, token_type="access")
    redis_client = get_redis()

    try:
        await revoke_token(credentials.credentials, token_type="access")
    finally:
        if redis_client is not None and token_data.session_id:
            await redis_client.delete(_session_key(token_data.session_id))

    log.info("auth.logout", user_id=str(current_user.id), session_id=token_data.session_id)
    return None


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(current_user=Depends(get_current_user)) -> list[SessionResponse]:
    """List active sessions for the current user."""
    redis_client = get_redis()
    if redis_client is None:
        return []

    sessions: list[SessionResponse] = []
    async for key in redis_client.scan_iter(match="auth:session:*"):
        raw_value = await redis_client.get(key)
        if not raw_value:
            continue
        session_id = key.split(":")[-1]
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            continue
        if payload.get("user_id") != str(current_user.id):
            continue

        sessions.append(
            SessionResponse(
                session_id=session_id,
                user_id=payload["user_id"],
                username=payload.get("metadata", {}).get("username", current_user.username),
                created_at=payload.get("created_at", datetime.now(timezone.utc).isoformat()),
                last_seen_at=payload.get("last_seen_at"),
                remember_me=bool(payload.get("metadata", {}).get("remember_me", False)),
                active=True,
            )
        )

    return sessions


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: str,
    current_user=Depends(get_current_user),
):
    """Revoke a specific active session."""
    redis_client = get_redis()
    if redis_client is not None:
        key = _session_key(session_id)
        raw_value = await redis_client.get(key)
        if raw_value:
            payload = json.loads(raw_value)
            if payload.get("user_id") != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot revoke another user's session")
        await redis_client.delete(key)
    return None


@router.post("/forgot-password", response_model=GenericMessageResponse)
async def forgot_password(request: ForgotPasswordRequest, db=Depends(get_db)) -> GenericMessageResponse:
    """Issue a password reset token."""
    user_service = UserService(db)
    user = await user_service.repository.get_by_email(request.email)

    if not user:
        return GenericMessageResponse(message="If the account exists, a reset token has been issued.")

    reset_token = str(uuid4())
    await _store_token_record(
        f"auth:reset:{reset_token}",
        {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "tenant_id": user.tenant_id,
        },
        RESET_TOKEN_SECONDS,
    )

    log.info("auth.password_reset.requested", user_id=str(user.id), email=user.email)
    return GenericMessageResponse(
        message="If the account exists, a reset token has been issued.",
        token=reset_token,
    )


@router.post("/reset-password", response_model=GenericMessageResponse)
async def reset_password(request: ResetPasswordRequest, db=Depends(get_db)) -> GenericMessageResponse:
    """Reset a password using a reset token."""
    validate_password_policy(request.new_password)

    redis_client = get_redis()
    if redis_client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Reset service unavailable")

    raw_value = await redis_client.get(f"auth:reset:{request.reset_token}")
    if not raw_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    payload = json.loads(raw_value)
    user_service = UserService(db)
    user = await user_service.get_user(UUID(payload["user_id"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await user_service.change_password(user.id, request.new_password)
    await redis_client.delete(f"auth:reset:{request.reset_token}")

    log.info("auth.password_reset.completed", user_id=str(user.id))
    return GenericMessageResponse(message="Password reset successfully")


@router.post("/verify-email", response_model=GenericMessageResponse)
async def verify_email(request: VerifyEmailRequest, db=Depends(get_db)) -> GenericMessageResponse:
    """Verify a user email address."""
    redis_client = get_redis()
    if redis_client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Verification service unavailable")

    raw_value = await redis_client.get(f"auth:verify:{request.verification_token}")
    if not raw_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token")

    payload = json.loads(raw_value)
    user_service = UserService(db)
    user = await user_service.get_user(UUID(payload["user_id"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = True
    await db.flush()
    await redis_client.delete(f"auth:verify:{request.verification_token}")

    log.info("auth.email_verified", user_id=str(user.id), email=user.email)
    return GenericMessageResponse(message="Email verified successfully")
