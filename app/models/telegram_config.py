"""Telegram Configuration entity model."""

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.application import Application


class TelegramConfiguration(Base, UUIDMixin, TimestampMixin):
    """Configuration for a Telegram Bot integration associated with an application."""

    __tablename__ = "telegram_configurations"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Encrypted via AES-256-GCM
    encrypted_bot_token: Mapped[str] = mapped_column(Text, nullable=False)
    default_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application", back_populates="telegram_configurations"
    )
