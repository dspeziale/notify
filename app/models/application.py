"""Application entity model."""

from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.permission import NotificationPermission
    from app.models.telegram_config import TelegramConfiguration
    from app.models.gmail_config import GmailConfiguration
    from app.models.notification import Notification


class Application(Base, UUIDMixin, TimestampMixin):
    """Client application registered in the gateway."""

    __tablename__ = "applications"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, disabled
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # Relationships
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey", back_populates="application", cascade="all, delete-orphan"
    )
    permissions: Mapped[list["NotificationPermission"]] = relationship(
        "NotificationPermission", back_populates="application", cascade="all, delete-orphan"
    )
    telegram_configurations: Mapped[list["TelegramConfiguration"]] = relationship(
        "TelegramConfiguration", back_populates="application", cascade="all, delete-orphan"
    )
    gmail_configurations: Mapped[list["GmailConfiguration"]] = relationship(
        "GmailConfiguration", back_populates="application", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="application", cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"
