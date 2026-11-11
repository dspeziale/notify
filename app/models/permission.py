"""Notification permission entity model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, UUIDMixin, utc_now

if TYPE_CHECKING:
    from app.models.application import Application


class NotificationPermission(Base, UUIDMixin):
    """Granular permissions granted to an application (e.g. 'telegram:send', 'gmail:send')."""

    __tablename__ = "notification_permissions"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application", back_populates="permissions"
    )

    __table_args__ = (
        UniqueConstraint("application_id", "permission", name="uq_app_permission"),
    )
