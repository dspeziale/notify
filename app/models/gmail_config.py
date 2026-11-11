"""Gmail / Email Configuration entity model supporting App Passwords (SMTP) and OAuth2."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.application import Application


class GmailConfiguration(Base, UUIDMixin, TimestampMixin):
    """Configuration for a Gmail / Email integration associated with an application."""

    __tablename__ = "gmail_configurations"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)

    # Auth type: "app_password" (Google App Password / SMTP) or "oauth2"
    auth_type: Mapped[str] = mapped_column(String(30), default="app_password", nullable=False)

    # SMTP / App Password settings
    smtp_host: Mapped[str | None] = mapped_column(String(100), default="smtp.gmail.com", nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, default=587, nullable=True)
    encrypted_app_password: Mapped[str | None] = mapped_column(Text, nullable=True)

    # OAuth2 credentials (optional if using App Password)
    encrypted_client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(
        String(255),
        default="https://www.googleapis.com/auth/gmail.send",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application", back_populates="gmail_configurations"
    )
