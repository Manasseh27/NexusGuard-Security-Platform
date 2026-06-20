"""
Enterprise configuration management with Pydantic Settings v2.
Supports environment-specific overrides, Vault integration, and secret rotation.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Any, Literal

from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")

    HOST: str = "postgres"
    PORT: int = 5432
    NAME: str = "cisco_security"
    USER: str = "cisco_app"
    PASSWORD: str = Field(default="changeme", repr=False)
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 40
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 1800
    ECHO: bool = False

    @field_validator("PASSWORD")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        if len(v.encode()) > 72:
            raise ValueError(
                "DB_PASSWORD exceeds 72 bytes. bcrypt cannot hash it safely. "
                "Shorten the password or use a different hashing scheme for DB credentials."
            )
        return v

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"

    @property
    def sync_url(self) -> str:
        return f"postgresql+psycopg2://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    HOST: str = "redis"
    PORT: int = 6379
    DB: int = 0
    PASSWORD: str | None = Field(default=None, repr=False)
    SSL: bool = False
    POOL_SIZE: int = 20
    TIMEOUT: int = 5

    # Cache TTLs (seconds)
    DEVICE_CACHE_TTL: int = 300
    COMPLIANCE_CACHE_TTL: int = 60
    USER_SESSION_TTL: int = 3600
    RATE_LIMIT_WINDOW: int = 60

    @property
    def url(self) -> str:
        auth = f":{self.PASSWORD}@" if self.PASSWORD else ""
        scheme = "rediss" if self.SSL else "redis"
        return f"{scheme}://{auth}{self.HOST}:{self.PORT}/{self.DB}"


class CelerySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CELERY_")

    BROKER_URL: str = "redis://redis:6379/1"
    RESULT_BACKEND: str = "redis://redis:6379/2"
    TASK_SERIALIZER: str = "json"
    RESULT_SERIALIZER: str = "json"
    ACCEPT_CONTENT: list[str] = ["json"]
    TIMEZONE: str = "UTC"
    ENABLE_UTC: bool = True
    TASK_SOFT_TIME_LIMIT: int = 300
    TASK_TIME_LIMIT: int = 600
    WORKER_PREFETCH_MULTIPLIER: int = 4
    WORKER_CONCURRENCY: int = 8


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JWT_")

    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(64), repr=False)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ISSUER: str = "nexusguard-security-platform"
    AUDIENCE: str = "nexusguard-security-api"


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_")

    # Provider configuration
    DEFAULT_PROVIDER: Literal["openai", "anthropic", "ollama", "azure"] = "openai"
    FALLBACK_PROVIDER: Literal["openai", "anthropic", "ollama", "azure"] | None = "ollama"

    # OpenAI
    OPENAI_API_KEY: str | None = Field(default=None, repr=False)
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = 4096

    # Anthropic Claude
    ANTHROPIC_API_KEY: str | None = Field(default=None, repr=False)
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # Ollama (local LLM)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_KEY: str | None = Field(default=None, repr=False)
    AZURE_OPENAI_DEPLOYMENT: str | None = None

    # RAG / Vector store
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    VECTOR_STORE_TYPE: Literal["pgvector", "chroma", "pinecone"] = "pgvector"
    PINECONE_API_KEY: str | None = Field(default=None, repr=False)
    PINECONE_INDEX: str = "nexusguard-security-kb"

    # Generation parameters
    TEMPERATURE: float = 0.1
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: int = 60


class SIEMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIEM_")

    # Splunk HEC
    SPLUNK_HEC_URL: str | None = None
    SPLUNK_HEC_TOKEN: str | None = Field(default=None, repr=False)
    SPLUNK_INDEX: str = "nexusguard_security"
    SPLUNK_SOURCETYPE: str = "nexusguard:security:platform"
    SPLUNK_BATCH_SIZE: int = 100
    SPLUNK_FLUSH_INTERVAL: int = 5

    # Microsoft Sentinel
    SENTINEL_WORKSPACE_ID: str | None = None
    SENTINEL_PRIMARY_KEY: str | None = Field(default=None, repr=False)
    SENTINEL_LOG_TYPE: str = "NexusGuardSecurityPlatform"

    # Elastic SIEM
    ELASTIC_URL: str | None = None
    ELASTIC_API_KEY: str | None = Field(default=None, repr=False)
    ELASTIC_INDEX_PREFIX: str = "nexusguard-security"

    # QRadar
    QRADAR_URL: str | None = None
    QRADAR_TOKEN: str | None = Field(default=None, repr=False)
    QRADAR_LOG_SOURCE_ID: str | None = None


class VaultSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VAULT_")

    ENABLED: bool = False
    ADDR: str = "https://vault.internal:8200"
    TOKEN: str | None = Field(default=None, repr=False)
    ROLE_ID: str | None = None
    SECRET_ID: str | None = Field(default=None, repr=False)
    MOUNT_PATH: str = "nexusguard-security"
    NAMESPACE: str | None = None


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OTEL_")

    EXPORTER_OTLP_ENDPOINT: str | None = None
    SAMPLE_RATE: float = 1.0
    PROPAGATORS: list[str] = ["tracecontext", "baggage"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Core ───────────────────────────────────────────────────────────────────
    SERVICE_NAME: str = "nexusguard-security-platform"
    VERSION: str = "2.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(64), repr=False)

    # ── Network ────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    ALLOWED_HOSTS: list[str] = ["*"]
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── Feature flags ──────────────────────────────────────────────────────────
    ENABLE_AI_COPILOT: bool = True
    ENABLE_SIEM_EXPORT: bool = True
    ENABLE_CONTINUOUS_MONITORING: bool = True
    ENABLE_AUTO_REMEDIATION: bool = False  # Requires explicit opt-in
    ENABLE_OPA_POLICIES: bool = True
    ENABLE_DEMO_DATA: bool = False

    # ── Rate limiting ──────────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_BURST: int = 20

    # ── Pagination ─────────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 25
    MAX_PAGE_SIZE: int = 500

    # ── Device execution ──────────────────────────────────────────────────────
    MAX_CONCURRENT_DEVICE_CONNECTIONS: int = 50
    DEVICE_SSH_TIMEOUT: int = 30
    DEVICE_COMMAND_TIMEOUT: int = 60
    DEVICE_MAX_RETRIES: int = 3
    DEVICE_RETRY_BACKOFF: float = 2.0

    # ── Compliance ────────────────────────────────────────────────────────────
    COMPLIANCE_POLLING_INTERVAL_SECONDS: int = 300
    COMPLIANCE_DRIFT_ALERT_THRESHOLD: float = 0.05  # 5% drift triggers alert
    COMPLIANCE_HISTORY_RETENTION_DAYS: int = 365

    # ── Audit ─────────────────────────────────────────────────────────────────
    AUDIT_LOG_RETENTION_DAYS: int = 2555  # 7 years for compliance
    AUDIT_IMMUTABLE: bool = True
    AUDIT_ENCRYPT_PII: bool = True

    # ── Sub-configurations ────────────────────────────────────────────────────
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    ai: AISettings = Field(default_factory=AISettings)
    siem: SIEMSettings = Field(default_factory=SIEMSettings)
    vault: VaultSettings = Field(default_factory=VaultSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    # ── Shortcuts (delegated properties) ─────────────────────────────────────
    @property
    def OTEL_EXPORTER_OTLP_ENDPOINT(self) -> str | None:
        return self.observability.EXPORTER_OTLP_ENDPOINT

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        return v.lower()

    @model_validator(mode="after")
    def production_guards(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY in ("changeme", ""):
                raise ValueError("SECRET_KEY must be set in production")
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
