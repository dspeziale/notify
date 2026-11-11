"""Notification tracking and delivery attempts models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, UUIDMixin, utc_now

if TYPE_CHECKING:
    from app.models.application import Application


class Notification(Base, UUIDMixin):
    """Central tracking record for each dispatched notification."""

    __tablename__ = "notifications"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # telegram, email
    configuration_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Status: pending, processing, sent, failed
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    recipient_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)

    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sanitized_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application", back_populates="notifications"
    )
    attempts: Mapped[list["NotificationAttempt"]] = relationship(
        "NotificationAttempt", back_populates="notification", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("application_id", "idempotency_key", name="uq_app_idempotency"),
        Index("ix_notifications_app_created", "application_id", "created_at"),
    )


class NotificationAttempt(Base, UUIDMixin):
    """Individual delivery attempt record for auditability and exponential backoff tracking."""

    __tablename__ = "notification_attempts"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failed
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    notification: Mapped["Notification"] = relationship(
        "Notification", back_populates="attempts"
    )
