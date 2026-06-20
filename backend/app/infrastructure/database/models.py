"""
SQLAlchemy ORM models — complete enterprise data layer.
Async-compatible, with proper relationships, indexes, and audit fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    pass


JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


# ── Enumerations ───────────────────────────────────────────────────────────

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SECURITY_ANALYST = "security_analyst"
    SOC_ANALYST = "soc_analyst"
    AUDITOR = "auditor"
    SECOPS_LEAD = "secops_lead"
    ENGINEER = "engineer"
    ANALYST = "analyst"
    VIEWER = "viewer"


class DeviceType(str, Enum):
    CISCO_IOS = "cisco_ios"
    CISCO_IOSXE = "cisco_iosxe"
    CISCO_IOSXR = "cisco_iosxr"
    CISCO_NXOS = "cisco_nxos"
    ARISTA_EOS = "arista_eos"
    JUNIPER_JUNOS = "juniper_junos"
    GENERIC = "generic"


class MonitoringState(str, Enum):
    HEALTHY = "healthy"
    DRIFTING = "drifting"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    REMEDIATING = "remediating"


class RuleSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ComplianceFramework(str, Enum):
    CIS = "cis"
    NIST_CSF = "nist_csf"
    NIST_800_53 = "nist_800_53"
    ISO_27001 = "iso_27001"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    MITRE_ATTACK = "mitre_attack"
    SOC2 = "soc2"
    CUSTOM = "custom"


class DriftSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemediationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class IncidentStatus(str, Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"


class NotificationType(str, Enum):
    INCIDENT = "incident"
    FINDING = "finding"
    COMPLIANCE = "compliance"
    ALERT = "alert"
    SYSTEM = "system"


class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


# ── Tables ─────────────────────────────────────────────────────────────────

class User(Base):
    """User account with RBAC."""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_service_account: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    custom_fields: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_users_tenant_role", "tenant_id", "role"),
    )


class Incident(Base):
    """Security incident lifecycle tracking."""
    __tablename__ = "incidents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_key: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[EventSeverity] = mapped_column(SQLEnum(EventSeverity), nullable=False, index=True)
    status: Mapped[IncidentStatus] = mapped_column(SQLEnum(IncidentStatus), default=IncidentStatus.NEW, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(128), default="platform", nullable=False)
    device_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True, index=True)
    finding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_to: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    owner_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    custom_fields: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    comments: Mapped[list["IncidentComment"]] = relationship("IncidentComment", back_populates="incident", cascade="all, delete-orphan")
    timeline_entries: Mapped[list["IncidentTimeline"]] = relationship("IncidentTimeline", back_populates="incident", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_incidents_tenant_status", "tenant_id", "status"),
        Index("ix_incidents_tenant_severity", "tenant_id", "severity"),
    )


class IncidentComment(Base):
    """Comments attached to incidents."""
    __tablename__ = "incident_comments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="comments")


class IncidentTimeline(Base):
    """Immutable incident timeline and audit trail entries."""
    __tablename__ = "incident_timeline"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="timeline_entries")


class Notification(Base):
    """User and system notifications for in-app and external delivery."""
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    incident_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False, index=True)
    channel: Mapped[NotificationChannel] = mapped_column(SQLEnum(NotificationChannel), default=NotificationChannel.IN_APP, nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    __table_args__ = (
        Index("ix_notifications_tenant_created", "tenant_id", "created_at"),
    )


class Device(Base):
    """Managed network device."""
    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    device_type: Mapped[DeviceType] = mapped_column(SQLEnum(DeviceType), default=DeviceType.GENERIC, nullable=False)
    site: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    credentials_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("device_credentials.id"), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    custom_fields: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    # Relationships
    monitoring_state: Mapped["DeviceMonitoringState | None"] = relationship("DeviceMonitoringState", back_populates="device", uselist=False, cascade="all, delete-orphan")
    compliance_scores: Mapped[list["ComplianceScore"]] = relationship("ComplianceScore", back_populates="device", cascade="all, delete-orphan")
    compliance_results: Mapped[list["ComplianceResult"]] = relationship("ComplianceResult", back_populates="device", cascade="all, delete-orphan")
    drift_events: Mapped[list["DriftEvent"]] = relationship("DriftEvent", back_populates="device", cascade="all, delete-orphan")
    remediation_jobs: Mapped[list["RemediationJob"]] = relationship("RemediationJob", back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_devices_tenant_site", "tenant_id", "site"),
        Index("ix_devices_tenant_type", "tenant_id", "device_type"),
    )


class DeviceCredentials(Base):
    """Encrypted device credentials."""
    __tablename__ = "device_credentials"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)  # ssh, snmp, api, etc
    encrypted_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class DeviceMonitoringState(Base):
    """Current monitoring state for a device."""
    __tablename__ = "device_monitoring_states"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id"), unique=True, nullable=False)
    monitoring_state: Mapped[MonitoringState] = mapped_column(SQLEnum(MonitoringState), default=MonitoringState.HEALTHY, nullable=False)
    current_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    baseline_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    current_config_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    last_polled: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_drift_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    poll_interval: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    frameworks: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="monitoring_state")


class ComplianceScore(Base):
    """Compliance score for a device against a framework."""
    __tablename__ = "compliance_scores"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    framework: Mapped[ComplianceFramework] = mapped_column(SQLEnum(ComplianceFramework), nullable=False)
    overall_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    weighted_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    compliance_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    baseline_delta: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="compliance_scores")

    __table_args__ = (
        Index("ix_compliance_scores_device_framework", "device_id", "framework"),
        Index("ix_compliance_scores_tenant_generated", "tenant_id", "generated_at"),
    )


class ComplianceResult(Base):
    """Individual compliance rule result."""
    __tablename__ = "compliance_results"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    framework: Mapped[ComplianceFramework] = mapped_column(SQLEnum(ComplianceFramework), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(256), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(512), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)  # pass, fail, warn, error, skipped
    severity: Mapped[RuleSeverity] = mapped_column(SQLEnum(RuleSeverity), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    remediation_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="compliance_results")

    __table_args__ = (
        Index("ix_compliance_results_device_framework", "device_id", "framework"),
        Index("ix_compliance_results_severity", "severity"),
    )


class DriftEvent(Base):
    """Compliance drift event — detected config/score changes."""
    __tablename__ = "drift_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    framework: Mapped[ComplianceFramework] = mapped_column(SQLEnum(ComplianceFramework), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(256), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(512), nullable=False)
    severity: Mapped[DriftSeverity] = mapped_column(SQLEnum(DriftSeverity), nullable=False, index=True)
    previous_result: Mapped[str] = mapped_column(String(32), nullable=False)
    current_result: Mapped[str] = mapped_column(String(32), nullable=False)
    score_delta: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    config_hash_before: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash_after: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    remediated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remediation_job_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("remediation_jobs.id"), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="drift_events")

    __table_args__ = (
        Index("ix_drift_events_device_framework", "device_id", "framework"),
        Index("ix_drift_events_unacknowledged", "acknowledged", "detected_at"),
    )


class RemediationJob(Base):
    """Remediation task for a device."""
    __tablename__ = "remediation_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    drift_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("drift_events.id"), nullable=True)
    status: Mapped[RemediationStatus] = mapped_column(SQLEnum(RemediationStatus), default=RemediationStatus.PENDING, nullable=False, index=True)
    remediation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_config: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    execution_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="remediation_jobs")


class AuditLog(Base):
    """Audit trail for user actions and system events."""
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_user_timestamp", "user_id", "timestamp"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_action", "action", "timestamp"),
    )


class SIEMEvent(Base):
    """SIEM event ingested from external sources."""
    __tablename__ = "siem_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    severity: Mapped[EventSeverity] = mapped_column(SQLEnum(EventSeverity), nullable=False, index=True)
    device_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    correlated_events: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    is_correlated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    __table_args__ = (
        Index("ix_siem_events_severity_timestamp", "severity", "event_timestamp"),
        Index("ix_siem_events_type_timestamp", "event_type", "event_timestamp"),
    )


class ComplianceException(Base):
    """Compliance exception — waived rule for a device."""
    __tablename__ = "compliance_exceptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(256), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(512), nullable=False)
    framework: Mapped[ComplianceFramework] = mapped_column(SQLEnum(ComplianceFramework), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", nullable=False, index=True)

    __table_args__ = (
        Index("ix_compliance_exceptions_active", "is_active", "expires_at"),
        Index("ix_compliance_exceptions_device_rule", "device_id", "rule_id"),
    )
