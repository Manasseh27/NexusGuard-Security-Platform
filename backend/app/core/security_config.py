"""
Security configuration and secrets management.
Validates all security-critical environment variables at startup.
"""

import secrets
from typing import Optional
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class SecurityConfig(BaseModel):
    """Security-related configuration."""

    # Secrets Management
    SECRET_KEY: str = Field(..., min_length=32, description="JWT signing key, use strong random value")
    API_KEY_SECRET: str = Field(..., min_length=32, description="API key signing secret")

    # HTTPS/TLS
    ENABLE_HTTPS: bool = Field(default=True, description="Enforce HTTPS in production")
    TLS_CERT_PATH: Optional[str] = Field(None, description="Path to TLS certificate")
    TLS_KEY_PATH: Optional[str] = Field(None, description="Path to TLS private key")

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed CORS origins",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True)

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS: int = Field(default=1000, description="Requests per window")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=3600)

    # IP Whitelisting
    IP_WHITELIST_ENABLED: bool = Field(default=False, description="Enable IP whitelist for sensitive endpoints")
    IP_WHITELIST: list[str] = Field(
        default_factory=list,
        description="Comma-separated IPs to whitelist",
    )

    # API Key Authentication
    API_KEY_AUTH_ENABLED: bool = Field(default=True, description="Enable API key authentication")
    REQUIRE_API_KEY: bool = Field(default=False, description="Require API key for all endpoints")

    # Session Security
    SESSION_TIMEOUT_MINUTES: int = Field(default=30)
    SESSION_SECURE_COOKIE: bool = Field(default=True, description="Only send cookies over HTTPS")
    SESSION_HTTP_ONLY: bool = Field(default=True, description="Prevent JavaScript access to session cookies")
    SESSION_SAME_SITE: str = Field(default="strict", description="SameSite cookie policy")

    # Password Policy
    PASSWORD_MIN_LENGTH: int = Field(default=12)
    PASSWORD_REQUIRE_UPPERCASE: bool = Field(default=True)
    PASSWORD_REQUIRE_LOWERCASE: bool = Field(default=True)
    PASSWORD_REQUIRE_NUMBERS: bool = Field(default=True)
    PASSWORD_REQUIRE_SPECIAL: bool = Field(default=True)
    PASSWORD_EXPIRY_DAYS: int = Field(default=90)

    # MFA
    MFA_REQUIRED: bool = Field(default=False, description="Require MFA for all users")
    MFA_METHODS: list[str] = Field(
        default_factory=lambda: ["totp", "email"],
        description="Supported MFA methods",
    )

    # Audit Logging
    AUDIT_LOG_ENABLED: bool = Field(default=True)
    AUDIT_LOG_RETENTION_DAYS: int = Field(default=365)
    LOG_SENSITIVE_DATA: bool = Field(default=False, description="Log potentially sensitive data (not recommended)")

    # LLM Security
    AI_API_KEY_REQUIRED: bool = Field(default=True)
    AI_PROVIDER: str = Field(default="openai", description="LLM provider: openai, anthropic, ollama")
    AI_RATE_LIMIT_REQUESTS: int = Field(default=20, description="AI requests per window")
    AI_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60)

    # Security Headers
    ENABLE_SECURITY_HEADERS: bool = Field(default=True)
    CSP_ENABLED: bool = Field(default=True, description="Enable Content-Security-Policy header")
    HSTS_ENABLED: bool = Field(default=True, description="Enable HSTS header")
    HSTS_MAX_AGE: int = Field(default=63072000, description="HSTS max-age in seconds (2 years)")

    # Request Validation
    MAX_REQUEST_SIZE_MB: int = Field(default=10, description="Maximum request body size in MB")
    XSS_PROTECTION_ENABLED: bool = Field(default=True)
    CSRF_PROTECTION_ENABLED: bool = Field(default=True)

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key is strong."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters (use: openssl rand -hex 32)")
        if v == "change-me":
            raise ValueError("SECRET_KEY must not be the default value")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: list[str]) -> list[str]:
        """Validate CORS origins."""
        if not v:
            raise ValueError("At least one CORS origin must be specified")
        # Ensure no wildcard in production
        if "*" in v:
            logger.warning("CORS wildcard (*) is insecure and should not be used in production")
        return v

    @model_validator(mode="after")
    def validate_https_config(self) -> "SecurityConfig":
        """Validate HTTPS configuration."""
        if self.ENABLE_HTTPS and not self.TLS_CERT_PATH:
            logger.warning("HTTPS enabled but TLS certificate path not set")
        return self

    class Config:
        """Pydantic config."""
        case_sensitive = True
        env_prefix = "SECURITY_"


class DatabaseSecurityConfig(BaseModel):
    """Database-specific security configuration."""

    # Connection Security
    DB_USE_SSL: bool = Field(default=True, description="Use SSL for database connections")
    DB_VERIFY_CERT: bool = Field(default=True, description="Verify database SSL certificate")
    DB_TIMEOUT_SECONDS: int = Field(default=30)

    # Credentials
    DB_PASSWORD_MIN_LENGTH: int = Field(default=16)
    DB_READONLY_USER: Optional[str] = Field(None, description="Read-only database user for certain services")

    # Backups
    BACKUP_ENCRYPTION_ENABLED: bool = Field(default=True)
    BACKUP_RETENTION_DAYS: int = Field(default=30)

    class Config:
        """Pydantic config."""
        case_sensitive = True
        env_prefix = "DB_"


@lru_cache(maxsize=1)
def get_security_config() -> SecurityConfig:
    """Load security config from environment variables."""
    import os
    from dotenv import load_dotenv

    # Load .env file if it exists
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    environment = os.getenv("ENVIRONMENT", "development").lower()

    def _secret(name: str, placeholder: str) -> str:
        value = os.getenv(name, "").strip()
        if value and value != placeholder:
            return value
        if environment == "production":
            return value or placeholder

        generated = secrets.token_urlsafe(48)
        logger.warning(
            "security.config.dev_secret_generated",
            variable=name,
            environment=environment,
        )
        return generated

    config = SecurityConfig(
        SECRET_KEY=_secret("SECRET_KEY", "change-me"),
        API_KEY_SECRET=_secret("API_KEY_SECRET", "change-me"),
        ENABLE_HTTPS=os.getenv("ENABLE_HTTPS", "true").lower() == "true",
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
        RATE_LIMIT_ENABLED=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
        MFA_REQUIRED=os.getenv("MFA_REQUIRED", "false").lower() == "true",
        AUDIT_LOG_ENABLED=os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true",
    )

    # Validate critical settings
    if config.SECRET_KEY == "change-me":
        logger.critical("⚠️  SECRET_KEY is still the default value! Generate a strong key immediately.")

    return config


def validate_security_startup():
    """Validate security configuration at startup."""
    try:
        config = get_security_config()
        logger.info(
            "security.config.loaded",
            https_enabled=config.ENABLE_HTTPS,
            cors_origins=len(config.CORS_ORIGINS),
            rate_limit_enabled=config.RATE_LIMIT_ENABLED,
            audit_enabled=config.AUDIT_LOG_ENABLED,
            mfa_required=config.MFA_REQUIRED,
        )
    except Exception as e:
        logger.critical(f"Security configuration validation failed: {e}")
        raise
