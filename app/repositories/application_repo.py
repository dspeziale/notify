"""Application repository for managing client applications and relationships."""

import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.application import Application
from app.models.permission import NotificationPermission
from app.repositories.base import BaseRepository


class ApplicationRepository(BaseRepository[Application]):
    """Application entity data access."""

    def __init__(self, session: AsyncSession):
        super().__init__(Application, session)

    async def get_by_id_with_relations(self, app_id: uuid.UUID) -> Application | None:
        """Retrieves an application including api_keys and permissions."""
        stmt = (
            select(Application)
            .options(
                selectinload(Application.api_keys),
                selectinload(Application.permissions),
            )
            .where(Application.id == app_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Application | None:
        """Finds application by unique name."""
        stmt = select(Application).where(Application.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all_with_relations(self, offset: int = 0, limit: int = 100) -> Sequence[Application]:
        """Lists applications with their eager-loaded relationships."""
        stmt = (
            select(Application)
            .options(
                selectinload(Application.api_keys),
                selectinload(Application.permissions),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def set_permissions(self, app_id: uuid.UUID, permissions: list[str]) -> None:
        """Replaces all permissions for an application."""
        # Delete existing permissions
        existing_stmt = select(NotificationPermission).where(NotificationPermission.application_id == app_id)
        existing = (await self.session.execute(existing_stmt)).scalars().all()
        for p in existing:
            await self.session.delete(p)

        # Add new permissions
        for perm in permissions:
            new_perm = NotificationPermission(application_id=app_id, permission=perm)
            self.session.add(new_perm)
        await self.session.flush()

