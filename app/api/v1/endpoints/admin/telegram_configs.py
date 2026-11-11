"""Administrative endpoints for Telegram Bot configurations."""

import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_client_ip, get_db, require_admin_auth
from app.schemas.common import APIResponse
from app.schemas.telegram_config import (
    TelegramConfigCreate,
    TelegramConfigResponse,
    TelegramConfigUpdate,
)
from app.services.audit_service import AuditService
from app.services.telegram_config_service import TelegramConfigService

router = APIRouter(
    prefix="/admin/telegram",
    tags=["Admin - Telegram Configurations"],
    dependencies=[Depends(require_admin_auth)],
)


@router.post("", response_model=APIResponse[TelegramConfigResponse], summary="Create Telegram configuration")
async def create_telegram_config(
    payload: TelegramConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Registers a new encrypted Telegram Bot configuration."""
    service = TelegramConfigService(db)
    audit_service = AuditService(db)

    config = await service.create_config(payload)

    await audit_service.log_event(
        actor_type="admin",
        action="telegram_config.create",
        resource_type="telegram_configuration",
        resource_id=str(config.id),
        details={"application_id": str(config.application_id), "name": config.name},
        ip_address=get_client_ip(request),
    )

    return APIResponse(
        data=TelegramConfigResponse.model_validate(config),
        message="Telegram configuration created successfully",
    )


@router.get("", response_model=APIResponse[list[TelegramConfigResponse]], summary="List Telegram configurations")
async def list_telegram_configs(
    application_id: uuid.UUID | None = Query(None, description="Optional filter by client application UUID"),
    offset: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Lists Telegram configurations for a given application."""
    service = TelegramConfigService(db)
    configs = await service.list_configs(application_id, offset=offset, limit=limit)
    return APIResponse(data=[TelegramConfigResponse.model_validate(c) for c in configs])


@router.get("/{config_id}", response_model=APIResponse[TelegramConfigResponse], summary="Get Telegram configuration")
async def get_telegram_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves safe Telegram configuration details."""
    service = TelegramConfigService(db)
    config = await service.get_config(config_id)
    return APIResponse(data=TelegramConfigResponse.model_validate(config))


@router.patch("/{config_id}", response_model=APIResponse[TelegramConfigResponse], summary="Update Telegram configuration")
async def update_telegram_config(
    config_id: uuid.UUID,
    payload: TelegramConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Updates Telegram configuration properties or rotates bot token."""
    service = TelegramConfigService(db)
    audit_service = AuditService(db)

    config = await service.update_config(config_id, payload)

    await audit_service.log_event(
        actor_type="admin",
        action="telegram_config.update",
        resource_type="telegram_configuration",
        resource_id=str(config.id),
        details=payload.model_dump(exclude={"bot_token"}, exclude_unset=True),
        ip_address=get_client_ip(request),
    )

    return APIResponse(
        data=TelegramConfigResponse.model_validate(config),
        message="Telegram configuration updated successfully",
    )


@router.post("/{config_id}/test", response_model=APIResponse[dict], summary="Test Telegram configuration")
async def test_telegram_config(
    config_id: uuid.UUID,
    chat_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Sends a test notification to verify Telegram bot connectivity."""
    service = TelegramConfigService(db)
    result = await service.test_configuration(config_id, chat_id=chat_id)
    return APIResponse(data=result, message="Telegram test executed")


@router.delete("/{config_id}", response_model=APIResponse[bool], summary="Delete Telegram configuration")
async def delete_telegram_config(
    config_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Permanently deletes a Telegram bot configuration."""
    service = TelegramConfigService(db)
    audit_service = AuditService(db)

    config = await service.get_config(config_id)
    name = config.name

    await service.delete_config(config_id)

    await audit_service.log_event(
        actor_type="admin",
        action="telegram_config.delete",
        resource_type="telegram_configuration",
        resource_id=str(config_id),
        details={"name": name},
        ip_address=get_client_ip(request),
    )

    return APIResponse(data=True, message=f"Telegram configuration '{name}' deleted successfully")

