"""Telegram Configuration repository with multi-tenant isolation."""

import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.telegram_config import TelegramConfiguration
from app.repositories.base import BaseRepository


class TelegramConfigRepository(BaseRepository[TelegramConfiguration]):
    """Data access for Telegram bot configurations."""

    def __init__(self, session: AsyncSession):
        super().__init__(TelegramConfiguration, session)

    async def get_by_id_and_app(
        self, config_id: uuid.UUID, app_id: uuid.UUID
    ) -> TelegramConfiguration | None:
        """Finds configuration guaranteeing tenant isolation."""
        stmt = select(TelegramConfiguration).where(
            TelegramConfiguration.id == config_id,
            TelegramConfiguration.application_id == app_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_app(
        self, app_id: uuid.UUID | None = None, offset: int = 0, limit: int = 100
    ) -> Sequence[TelegramConfiguration]:
        """Lists configurations, optionally filtered by application."""
        stmt = select(TelegramConfiguration)
        if app_id:
            stmt = stmt.where(TelegramConfiguration.application_id == app_id)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

