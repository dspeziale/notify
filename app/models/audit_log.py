"""Audit log entity model."""

from datetime import datetime
from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base, UUIDMixin, utc_now


class AuditLog(Base, UUIDMixin):
    """Immutable audit trail for all security, configuration, and administrative operations."""

    __tablename__ = "audit_logs"

    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)  # admin, application, system
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failure
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON payload, redacted
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
    )
