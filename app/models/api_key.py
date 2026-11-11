"""API Key entity model."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, UUIDMixin, utc_now

if TYPE_CHECKING:
    from app.models.application import Application


class APIKey(Base, UUIDMixin):
    """Cryptographically secure API key metadata and HMAC hash."""

    __tablename__ = "api_keys"

    application_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # The public key prefix (e.g. ng_live_a1b2c3d4) is indexed for fast lookup
    key_prefix: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # Stored strictly as HMAC-SHA256 with secret pepper
    hashed_key: Mapped[str] = mapped_column(String(128), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    application: Mapped["Application | None"] = relationship(
        "Application", back_populates="api_keys"
    )

    __table_args__ = (
        Index("ix_api_keys_prefix_active", "key_prefix", "is_active"),
    )

    @property
    def is_valid(self) -> bool:
        if not self.is_active or self.revoked_at is not None:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True
