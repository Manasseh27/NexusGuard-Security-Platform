"""Initial database schema — users, devices, compliance, auditing."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    monitoring_state_enum = postgresql.ENUM(
        "healthy", "drifting", "degraded", "unreachable", "remediating",
        name="monitoringstate", create_type=False
    )
    rule_severity_enum = postgresql.ENUM(
        "critical", "high", "medium", "low", "informational",
        name="ruleseverity", create_type=False
    )
    compliance_framework_enum = postgresql.ENUM(
        "cis", "nist_csf", "nist_800_53", "iso_27001", "pci_dss", "hipaa", "mitre_attack", "soc2", "custom",
        name="complianceframework", create_type=False
    )
    drift_severity_enum = postgresql.ENUM(
        "critical", "high", "medium", "low",
        name="driftseverity", create_type=False
    )
    device_type_enum = postgresql.ENUM(
        "cisco_ios", "cisco_iosxe", "cisco_iosxr", "cisco_nxos", "arista_eos", "juniper_junos", "generic",
        name="devicetype", create_type=False
    )
    user_role_enum = postgresql.ENUM(
        "admin", "secops_lead", "engineer", "analyst", "viewer",
        name="userrole", create_type=False
    )
    remediation_status_enum = postgresql.ENUM(
        "pending", "in_progress", "succeeded", "failed", "cancelled",
        name="remediationstatus", create_type=False
    )
    event_severity_enum = postgresql.ENUM(
        "critical", "high", "medium", "low", "informational",
        name="eventseverity", create_type=False
    )

    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.LargeBinary(), nullable=False),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_service_account", sa.Boolean(), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_tenant_role", "users", ["tenant_id", "role"])

    # Device credentials table
    op.create_table(
        "device_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("encrypted_data", sa.LargeBinary(), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_device_credentials_tenant_id", "device_credentials", ["tenant_id"])

    # Devices table
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("hostname", sa.String(256), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("device_type", device_type_enum, nullable=False),
        sa.Column("site", sa.String(128), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("credentials_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["credentials_id"], ["device_credentials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index("ix_devices_device_id", "devices", ["device_id"], unique=True)
    op.create_index("ix_devices_hostname", "devices", ["hostname"])
    op.create_index("ix_devices_ip_address", "devices", ["ip_address"])
    op.create_index("ix_devices_tenant_id", "devices", ["tenant_id"])
    op.create_index("ix_devices_site", "devices", ["site"])
    op.create_index("ix_devices_tenant_site", "devices", ["tenant_id", "site"])
    op.create_index("ix_devices_tenant_type", "devices", ["tenant_id", "device_type"])

    # Device monitoring states table
    op.create_table(
        "device_monitoring_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monitoring_state", monitoring_state_enum, nullable=False),
        sa.Column("current_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("baseline_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("current_config_hash", sa.String(64), nullable=False),
        sa.Column("last_polled", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("active_drift_count", sa.Integer(), nullable=False),
        sa.Column("poll_interval", sa.Integer(), nullable=False),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frameworks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index("ix_device_monitoring_states_device_id", "device_monitoring_states", ["device_id"], unique=True)

    # Compliance scores table
    op.create_table(
        "compliance_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("framework", compliance_framework_enum, nullable=False),
        sa.Column("overall_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("weighted_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("compliance_percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("pass_count", sa.Integer(), nullable=False),
        sa.Column("fail_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("critical_failures", sa.Integer(), nullable=False),
        sa.Column("baseline_delta", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_scores_device_id", "compliance_scores", ["device_id"])
    op.create_index("ix_compliance_scores_device_framework", "compliance_scores", ["device_id", "framework"])
    op.create_index("ix_compliance_scores_generated_at", "compliance_scores", ["generated_at"])
    op.create_index("ix_compliance_scores_tenant_generated", "compliance_scores", ["tenant_id", "generated_at"])

    # Compliance results table
    op.create_table(
        "compliance_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("framework", compliance_framework_enum, nullable=False),
        sa.Column("rule_id", sa.String(256), nullable=False),
        sa.Column("rule_name", sa.String(512), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("severity", rule_severity_enum, nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("remediation_guidance", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_results_device_id", "compliance_results", ["device_id"])
    op.create_index("ix_compliance_results_device_framework", "compliance_results", ["device_id", "framework"])
    op.create_index("ix_compliance_results_evaluated_at", "compliance_results", ["evaluated_at"])
    op.create_index("ix_compliance_results_severity", "compliance_results", ["severity"])

    # Drift events table
    op.create_table(
        "drift_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("framework", compliance_framework_enum, nullable=False),
        sa.Column("rule_id", sa.String(256), nullable=False),
        sa.Column("rule_name", sa.String(512), nullable=False),
        sa.Column("severity", drift_severity_enum, nullable=False),
        sa.Column("previous_result", sa.String(32), nullable=False),
        sa.Column("current_result", sa.String(32), nullable=False),
        sa.Column("score_delta", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("config_hash_before", sa.String(64), nullable=False),
        sa.Column("config_hash_after", sa.String(64), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("remediated", sa.Boolean(), nullable=False),
        sa.Column("remediation_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_drift_events_device_id", "drift_events", ["device_id"])
    op.create_index("ix_drift_events_device_framework", "drift_events", ["device_id", "framework"])
    op.create_index("ix_drift_events_severity", "drift_events", ["severity"])
    op.create_index("ix_drift_events_detected_at", "drift_events", ["detected_at"])
    op.create_index("ix_drift_events_unacknowledged", "drift_events", ["acknowledged", "detected_at"])

    # Remediation jobs table
    op.create_table(
        "remediation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("drift_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", remediation_status_enum, nullable=False),
        sa.Column("remediation_type", sa.String(64), nullable=False),
        sa.Column("target_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("execution_output", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["drift_event_id"], ["drift_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remediation_jobs_device_id", "remediation_jobs", ["device_id"])
    op.create_index("ix_remediation_jobs_status", "remediation_jobs", ["status"])

    # Audit logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(256), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_user_timestamp", "audit_logs", ["user_id", "timestamp"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action", "timestamp"])

    # SIEM events table
    op.create_table(
        "siem_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(256), nullable=False),
        sa.Column("severity", event_severity_enum, nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correlated_events", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_correlated", sa.Boolean(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_siem_events_event_type", "siem_events", ["event_type"])
    op.create_index("ix_siem_events_severity", "siem_events", ["severity"])
    op.create_index("ix_siem_events_is_correlated", "siem_events", ["is_correlated"])
    op.create_index("ix_siem_events_ingested_at", "siem_events", ["ingested_at"])
    op.create_index("ix_siem_events_event_timestamp", "siem_events", ["event_timestamp"])
    op.create_index("ix_siem_events_severity_timestamp", "siem_events", ["severity", "event_timestamp"])
    op.create_index("ix_siem_events_type_timestamp", "siem_events", ["event_type", "event_timestamp"])

    # Compliance exceptions table
    op.create_table(
        "compliance_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", sa.String(256), nullable=False),
        sa.Column("rule_name", sa.String(512), nullable=False),
        sa.Column("framework", compliance_framework_enum, nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_exceptions_device_id", "compliance_exceptions", ["device_id"])
    op.create_index("ix_compliance_exceptions_expires_at", "compliance_exceptions", ["expires_at"])
    op.create_index("ix_compliance_exceptions_is_active", "compliance_exceptions", ["is_active"])
    op.create_index("ix_compliance_exceptions_active", "compliance_exceptions", ["is_active", "expires_at"])
    op.create_index("ix_compliance_exceptions_device_rule", "compliance_exceptions", ["device_id", "rule_id"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("compliance_exceptions")
    op.drop_table("siem_events")
    op.drop_table("audit_logs")
    op.drop_table("remediation_jobs")
    op.drop_table("drift_events")
    op.drop_table("compliance_results")
    op.drop_table("compliance_scores")
    op.drop_table("device_monitoring_states")
    op.drop_table("devices")
    op.drop_table("device_credentials")
    op.drop_table("users")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS eventseverity")
    op.execute("DROP TYPE IF EXISTS remediationstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS devicetype")
    op.execute("DROP TYPE IF EXISTS driftseverity")
    op.execute("DROP TYPE IF EXISTS complianceframework")
    op.execute("DROP TYPE IF EXISTS ruleseverity")
    op.execute("DROP TYPE IF EXISTS monitoringstate")
