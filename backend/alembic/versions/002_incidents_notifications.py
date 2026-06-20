"""Add incident management and notification tables

Revision ID: 002_incidents_notifications
Revises: 001_initial_schema
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "002_incidents_notifications"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'security_analyst'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'soc_analyst'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'auditor'")

    incident_status_enum = postgresql.ENUM(
        "new", "assigned", "investigating", "contained", "resolved", "closed",
        name="incidentstatus",
        create_type=False,
    )
    notification_type_enum = postgresql.ENUM(
        "incident", "finding", "compliance", "alert", "system",
        name="notificationtype",
        create_type=False,
    )
    notification_channel_enum = postgresql.ENUM(
        "in_app", "email", "webhook",
        name="notificationchannel",
        create_type=False,
    )
    notification_status_enum = postgresql.ENUM(
        "pending", "sent", "failed", "read",
        name="notificationstatus",
        create_type=False,
    )

    bind = op.get_bind()
    incident_status_enum.create(bind, checkfirst=True)
    notification_type_enum.create(bind, checkfirst=True)
    notification_channel_enum.create(bind, checkfirst=True)
    notification_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_key", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.Enum("critical", "high", "medium", "low", "informational", name="eventseverity"), nullable=False),
        sa.Column("status", incident_status_enum, nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_key"),
    )
    op.create_index("ix_incidents_incident_key", "incidents", ["incident_key"], unique=True)
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_device_id", "incidents", ["device_id"])
    op.create_index("ix_incidents_assigned_to", "incidents", ["assigned_to"])
    op.create_index("ix_incidents_owner_id", "incidents", ["owner_id"])
    op.create_index("ix_incidents_tenant_id", "incidents", ["tenant_id"])
    op.create_index("ix_incidents_tenant_status", "incidents", ["tenant_id", "status"])
    op.create_index("ix_incidents_tenant_severity", "incidents", ["tenant_id", "severity"])

    op.create_table(
        "incident_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_comments_incident_id", "incident_comments", ["incident_id"])
    op.create_index("ix_incident_comments_tenant_id", "incident_comments", ["tenant_id"])

    op.create_table(
        "incident_timeline",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_timeline_incident_id", "incident_timeline", ["incident_id"])
    op.create_index("ix_incident_timeline_tenant_id", "incident_timeline", ["tenant_id"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notification_type", notification_type_enum, nullable=False),
        sa.Column("channel", notification_channel_enum, nullable=False),
        sa.Column("status", notification_status_enum, nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_incident_id", "notifications", ["incident_id"])
    op.create_index("ix_notifications_event_type", "notifications", ["event_type"])
    op.create_index("ix_notifications_notification_type", "notifications", ["notification_type"])
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_tenant_id", "notifications", ["tenant_id"])
    op.create_index("ix_notifications_tenant_created", "notifications", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("incident_timeline")
    op.drop_table("incident_comments")
    op.drop_table("incidents")

    op.execute("DROP TYPE IF EXISTS notificationstatus")
    op.execute("DROP TYPE IF EXISTS notificationchannel")
    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS incidentstatus")
