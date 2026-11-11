"""Application management service for administrative control."""

from datetime import datetime, timedelta, timezone
import uuid
from typing import Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import generate_api_key
from app.models.api_key import APIKey
from app.models.application import Application
from app.models.permission import NotificationPermission
from app.repositories.api_key_repo import APIKeyRepository
from app.repositories.application_repo import ApplicationRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate


class ApplicationService:
    """Manages application registration, configuration, and API keys."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.app_repo = ApplicationRepository(session)
        self.api_key_repo = APIKeyRepository(session)

    async def create_application(self, data: ApplicationCreate) -> tuple[Application, str]:
        """Registers a new client application with its initial API Key.

        Returns:
            (application, raw_api_key)
        """
        existing = await self.app_repo.get_by_name(data.name)
        if existing:
            raise ConflictException(f"Application with name '{data.name}' already exists")

        app = Application(
            name=data.name,
            description=data.description,
            status="active",
            rate_limit_per_minute=data.rate_limit_per_minute,
        )
        await self.app_repo.add(app)

        # Generate initial API Key
        raw_key, key_prefix, hashed_key = generate_api_key()
        api_key = APIKey(
            application_id=app.id,
            name="Default API Key",
            key_prefix=key_prefix,
            hashed_key=hashed_key,
            is_admin=False,
            is_active=True,
        )
        await self.api_key_repo.add(api_key)

        # Set permissions
        for perm in data.permissions:
            new_perm = NotificationPermission(application_id=app.id, permission=perm)
            self.session.add(new_perm)

        await self.session.flush()
        # Reload with relations
        reloaded = await self.app_repo.get_by_id_with_relations(app.id)
        return reloaded, raw_key

    async def regenerate_api_key(
        self, app_id: uuid.UUID, key_name: str = "Regenerated Key"
    ) -> tuple[APIKey, str]:
        """Revokes all existing keys for an application and generates a fresh one."""
        app = await self.app_repo.get_by_id(app_id)
        if not app:
            raise NotFoundException(f"Application {app_id} not found")

        # Revoke previous active keys
        await self.api_key_repo.revoke_all_for_app(app_id)

        # Generate new key
        raw_key, key_prefix, hashed_key = generate_api_key()
        new_key = APIKey(
            application_id=app_id,
            name=key_name,
            key_prefix=key_prefix,
            hashed_key=hashed_key,
            is_admin=False,
            is_active=True,
        )
        await self.api_key_repo.add(new_key)
        return new_key, raw_key

    async def revoke_api_key(self, key_id: uuid.UUID) -> None:
        """Revokes a specific API Key."""
        success = await self.api_key_repo.revoke_key(key_id)
        if not success:
            raise NotFoundException(f"API key {key_id} not found")

    async def update_application(self, app_id: uuid.UUID, data: ApplicationUpdate) -> Application:
        """Updates application parameters."""
        app = await self.app_repo.get_by_id_with_relations(app_id)
        if not app:
            raise NotFoundException(f"Application {app_id} not found")

        if data.name and data.name != app.name:
            existing = await self.app_repo.get_by_name(data.name)
            if existing and existing.id != app.id:
                raise ConflictException(f"Application name '{data.name}' is already taken")
            app.name = data.name

        if data.description is not None:
            app.description = data.description
        if data.status:
            app.status = data.status
        if data.rate_limit_per_minute is not None:
            app.rate_limit_per_minute = data.rate_limit_per_minute
        if data.permissions is not None:
            await self.app_repo.set_permissions(app_id, data.permissions)

        await self.session.flush()
        return await self.app_repo.get_by_id_with_relations(app_id)

    async def get_application(self, app_id: uuid.UUID) -> Application:
        """Retrieves an application by ID."""
        app = await self.app_repo.get_by_id_with_relations(app_id)
        if not app:
            raise NotFoundException(f"Application {app_id} not found")
        return app

    async def list_applications(self, offset: int = 0, limit: int = 100) -> Sequence[Application]:
        """Lists all registered applications."""
        return await self.app_repo.list_all_with_relations(offset=offset, limit=limit)

