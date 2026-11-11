"""Notification tracking repository for status, attempts, and idempotency."""

import uuid
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.notification import Notification, NotificationAttempt
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    """Data access for notifications and delivery attempts."""

    def __init__(self, session: AsyncSession):
        super().__init__(Notification, session)

    async def get_by_id_and_app(
        self, notification_id: uuid.UUID, app_id: uuid.UUID
    ) -> Notification | None:
        """Finds notification belonging to specific application with all attempts."""
        stmt = (
            select(Notification)
            .options(selectinload(Notification.attempts))
            .where(
                Notification.id == notification_id,
                Notification.application_id == app_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(
        self, app_id: uuid.UUID, idempotency_key: str
    ) -> Notification | None:
        """Finds existing notification by application ID and idempotency key."""
        stmt = (
            select(Notification)
            .options(selectinload(Notification.attempts))
            .where(
                Notification.application_id == app_id,
                Notification.idempotency_key == idempotency_key,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_app(
        self, app_id: uuid.UUID, offset: int = 0, limit: int = 50
    ) -> Sequence[Notification]:
        """Lists notifications for a specific application in descending order."""
        stmt = (
            select(Notification)
            .options(selectinload(Notification.attempts))
            .where(Notification.application_id == app_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add_attempt(
        self,
        notification_id: uuid.UUID,
        attempt_number: int,
        status: str,
        response_code: int | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> NotificationAttempt:
        """Appends an attempt record for a notification."""
        attempt = NotificationAttempt(
            notification_id=notification_id,
            attempt_number=attempt_number,
            status=status,
            response_code=response_code,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def update_status(
        self,
        notification: Notification,
        status: str,
        attempts_count: int,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> Notification:
        """Updates the status, attempt count, and error state."""
        notification.status = status
        notification.attempts_count = attempts_count
        notification.error_code = error_code
        notification.sanitized_error_message = error_message
        if status == "sent":
            notification.sent_at = datetime.now(timezone.utc)
        await self.session.flush()
        return notification

