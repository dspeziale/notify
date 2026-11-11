"""Telegram configuration service handling AES-256-GCM encryption and management."""

import uuid
from typing import Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.encryption import encryption_service
from app.core.exceptions import NotFoundException
from app.models.telegram_config import TelegramConfiguration
from app.providers.telegram import TelegramProvider
from app.repositories.application_repo import ApplicationRepository
from app.repositories.telegram_config_repo import TelegramConfigRepository
from app.schemas.telegram_config import TelegramConfigCreate, TelegramConfigUpdate


class TelegramConfigService:
    """Manages Telegram bot configurations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TelegramConfigRepository(session)
        self.app_repo = ApplicationRepository(session)

    async def create_config(self, data: TelegramConfigCreate) -> TelegramConfiguration:
        """Encrypts bot token and creates configuration."""
        app = await self.app_repo.get_by_id(data.application_id)
        if not app:
            raise NotFoundException(f"Application {data.application_id} not found")

        encrypted_token = encryption_service.encrypt(data.bot_token)
        config = TelegramConfiguration(
            application_id=data.application_id,
            name=data.name,
            encrypted_bot_token=encrypted_token,
            default_chat_id=data.default_chat_id,
            is_active=data.is_active,
        )
        await self.repo.add(config)
        return config

    async def update_config(
        self, config_id: uuid.UUID, data: TelegramConfigUpdate, app_id: uuid.UUID | None = None
    ) -> TelegramConfiguration:
        """Updates configuration, re-encrypting token if modified."""
        if app_id:
            config = await self.repo.get_by_id_and_app(config_id, app_id)
        else:
            config = await self.repo.get_by_id(config_id)

        if not config:
            raise NotFoundException(f"Telegram configuration {config_id} not found")

        if data.name:
            config.name = data.name
        if data.default_chat_id is not None:
            config.default_chat_id = data.default_chat_id
        if data.is_active is not None:
            config.is_active = data.is_active
        if data.bot_token:
            config.encrypted_bot_token = encryption_service.encrypt(data.bot_token)

        await self.session.flush()
        return config

    async def get_config(
        self, config_id: uuid.UUID, app_id: uuid.UUID | None = None
    ) -> TelegramConfiguration:
        """Retrieves configuration by ID."""
        if app_id:
            config = await self.repo.get_by_id_and_app(config_id, app_id)
        else:
            config = await self.repo.get_by_id(config_id)

        if not config:
            raise NotFoundException(f"Telegram configuration {config_id} not found")
        return config

    async def list_configs(
        self, app_id: uuid.UUID, offset: int = 0, limit: int = 100
    ) -> Sequence[TelegramConfiguration]:
        """Lists configurations for an application."""
        return await self.repo.list_by_app(app_id, offset=offset, limit=limit)

    async def get_decrypted_token(self, config: TelegramConfiguration) -> str:
        """Decrypts the bot token for provider consumption."""
        return encryption_service.decrypt(config.encrypted_bot_token)

    async def test_configuration(
        self, config_id: uuid.UUID, chat_id: str | None = None
    ) -> dict[str, str | bool]:
        """Tests telegram bot token by sending a test message."""
        config = await self.get_config(config_id)
        target_chat_id = chat_id or config.default_chat_id
        if not target_chat_id:
            return {
                "success": False,
                "message": "No chat_id provided and no default_chat_id configured",
            }

        token = await self.get_decrypted_token(config)
        provider = TelegramProvider(bot_token=token)
        result = await provider.send({
            "chat_id": target_chat_id,
            "message": "🚀 [Notification Gateway] Test message - Integration successful!",
            "parse_mode": "HTML",
        })
        return {
            "success": result.success,
            "message": result.error_message or f"Test message delivered (ID: {result.provider_message_id})",
        }

