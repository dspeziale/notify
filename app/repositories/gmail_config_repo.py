"""Gmail Configuration repository with multi-tenant isolation."""

import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.gmail_config import GmailConfiguration
from app.repositories.base import BaseRepository


class GmailConfigRepository(BaseRepository[GmailConfiguration]):
    """Data access for Gmail OAuth2 configurations."""

    def __init__(self, session: AsyncSession):
        super().__init__(GmailConfiguration, session)

    async def get_by_id_and_app(
        self, config_id: uuid.UUID, app_id: uuid.UUID
    ) -> GmailConfiguration | None:
        """Finds configuration guaranteeing tenant isolation."""
        stmt = select(GmailConfiguration).where(
            GmailConfiguration.id == config_id,
            GmailConfiguration.application_id == app_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_app(
        self, app_id: uuid.UUID | None = None, offset: int = 0, limit: int = 100
    ) -> Sequence[GmailConfiguration]:
        """Lists configurations, optionally filtered by application."""
        stmt = select(GmailConfiguration)
        if app_id:
            stmt = stmt.where(GmailConfiguration.application_id == app_id)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

