"""API Key repository for key validation, lookup, and revocation."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.api_key import APIKey
from app.repositories.base import BaseRepository


class APIKeyRepository(BaseRepository[APIKey]):
    """Data access for API Keys."""

    def __init__(self, session: AsyncSession):
        super().__init__(APIKey, session)

    async def get_by_prefix(self, key_prefix: str) -> APIKey | None:
        """Finds active API key by its public prefix."""
        stmt = (
            select(APIKey)
            .options(
                selectinload(APIKey.application),
            )
            .where(
                APIKey.key_prefix == key_prefix,
                APIKey.is_active == True,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_key(self, key_id: uuid.UUID) -> bool:
        """Revokes an API key immediately."""
        key = await self.get_by_id(key_id)
        if not key:
            return False
        key.is_active = False
        key.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def revoke_all_for_app(self, application_id: uuid.UUID) -> int:
        """Revokes all active API keys for an application."""
        stmt = select(APIKey).where(
            APIKey.application_id == application_id,
            APIKey.is_active == True,
        )
        keys = (await self.session.execute(stmt)).scalars().all()
        now = datetime.now(timezone.utc)
        for k in keys:
            k.is_active = False
            k.revoked_at = now
        await self.session.flush()
        return len(keys)

