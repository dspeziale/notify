"""SQLAlchemy declarative base and common model mixins."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Returns the current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""
    pass


class TimestampMixin:
    """Provides created_at and updated_at UTC timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class UUIDMixin:
    """Provides a primary key UUID column."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
