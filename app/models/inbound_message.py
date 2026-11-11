"""Inbound message entity model for incoming messages (Telegram, Gmail/Email)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, UUIDMixin, utc_now

if TYPE_CHECKING:
    from app.models.application import Application


class InboundMessage(Base, UUIDMixin):
    """Stores incoming messages received from Telegram Webhook / Polling and Gmail / IMAP webhooks."""

    __tablename__ = "inbound_messages"

    application_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # telegram, gmail, email
    configuration_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    sender_identifier: Mapped[str] = mapped_column(String(255), nullable=False)  # Chat ID or email address
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status: received, processed, forwarded, failed
    status: Mapped[str] = mapped_column(String(20), default="received", nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    # Relationships
    application: Mapped["Application | None"] = relationship("Application")

    __table_args__ = (
        Index("ix_inbound_provider_created", "provider", "created_at"),
    )

