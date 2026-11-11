"""Audit Log repository for recording administrative operations."""

from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Data access for immutable audit logs."""

    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

    async def list_recent(self, offset: int = 0, limit: int = 100) -> Sequence[AuditLog]:
        """Lists audit logs in descending chronological order."""
        stmt = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

