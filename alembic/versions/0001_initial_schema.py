"""Initial database schema migration for Notification Gateway.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-09 12:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. applications
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_applications_name", "applications", ["name"])

    # 2. api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("hashed_key", sa.String(length=128), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_api_keys_prefix_active", "api_keys", ["key_prefix", "is_active"])
    op.create_index("ix_api_keys_application_id", "api_keys", ["application_id"])

    # 3. notification_permissions
    op.create_table(
        "notification_permissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("application_id", "permission", name="uq_app_permission"),
    )
    op.create_index("ix_permissions_app_id", "notification_permissions", ["application_id"])

    # 4. telegram_configurations
    op.create_table(
        "telegram_configurations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("encrypted_bot_token", sa.Text(), nullable=False),
        sa.Column("default_chat_id", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_telegram_app_id", "telegram_configurations", ["application_id"])

    # 5. gmail_configurations
    op.create_table(
        "gmail_configurations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("auth_type", sa.String(length=30), nullable=False, server_default="app_password"),
        sa.Column("smtp_host", sa.String(length=100), nullable=True, server_default="smtp.gmail.com"),
        sa.Column("smtp_port", sa.Integer(), nullable=True, server_default="587"),
        sa.Column("encrypted_app_password", sa.Text(), nullable=True),
        sa.Column("encrypted_client_id", sa.Text(), nullable=True),
        sa.Column("encrypted_client_secret", sa.Text(), nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.String(length=255), nullable=False, server_default="https://www.googleapis.com/auth/gmail.send"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_gmail_app_id", "gmail_configurations", ["application_id"])

    # 6. notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("configuration_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("recipient_summary", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("sanitized_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("application_id", "idempotency_key", name="uq_app_idempotency"),
    )
    op.create_index("ix_notifications_app_created", "notifications", ["application_id", "created_at"])
    op.create_index("ix_notifications_idempotency", "notifications", ["idempotency_key"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    # 7. notification_attempts
    op.create_table(
        "notification_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("notification_id", sa.Uuid(), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attempts_notification_id", "notification_attempts", ["notification_id"])

    # 8. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_id", "created_at"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notification_attempts")
    op.drop_table("notifications")
    op.drop_table("gmail_configurations")
    op.drop_table("telegram_configurations")
    op.drop_table("notification_permissions")
    op.drop_table("api_keys")
    op.drop_table("applications")

