"""Base repository providing generic CRUD operations with SQLAlchemy 2.0 AsyncSession."""

import uuid
from typing import Generic, Sequence, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic repository implementation."""

    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        """Finds an entity by its primary key UUID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, offset: int = 0, limit: int = 100) -> Sequence[ModelType]:
        """Lists entities with pagination."""
        result = await self.session.execute(
            select(self.model).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def add(self, entity: ModelType) -> ModelType:
        """Stages an entity for insertion."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelType) -> None:
        """Deletes an entity."""
        await self.session.delete(entity)
        await self.session.flush()

