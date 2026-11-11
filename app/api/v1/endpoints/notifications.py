"""Notification dispatch and status tracking REST API endpoints."""

import uuid
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_application, get_db
from app.models.application import Application
from app.schemas.common import APIResponse
from app.schemas.notification import (
    EmailNotificationRequest,
    NotificationDetailResponse,
    NotificationResponse,
    TelegramNotificationRequest,
    UnifiedNotificationRequest,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post(
    "/telegram",
    response_model=APIResponse[NotificationResponse],
    summary="Send a Telegram notification",
)
async def send_telegram_notification(
    payload: TelegramNotificationRequest,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    app: Application = Depends(get_current_application),
    db: AsyncSession = Depends(get_db),
):
    """Sends a Telegram notification to the specified or default chat."""
    idempotency_key = x_idempotency_key or payload.idempotency_key
    service = NotificationService(db)

    notification = await service.dispatch(
        application=app,
        provider_name="telegram",
        configuration_id=payload.configuration_id,
        payload=payload.model_dump(),
        idempotency_key=idempotency_key,
    )
    return APIResponse(data=NotificationResponse.model_validate(notification))


@router.post(
    "/email",
    response_model=APIResponse[NotificationResponse],
    summary="Send an Email via Gmail API",
)
async def send_email_notification(
    payload: EmailNotificationRequest,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    app: Application = Depends(get_current_application),
    db: AsyncSession = Depends(get_db),
):
    """Sends an email notification via Google Gmail API."""
    idempotency_key = x_idempotency_key or payload.idempotency_key
    service = NotificationService(db)

    notification = await service.dispatch(
        application=app,
        provider_name="email",
        configuration_id=payload.configuration_id,
        payload=payload.model_dump(),
        idempotency_key=idempotency_key,
    )
    return APIResponse(data=NotificationResponse.model_validate(notification))


@router.post(
    "",
    response_model=APIResponse[NotificationResponse],
    summary="Unified notification endpoint",
)
async def send_unified_notification(
    payload: UnifiedNotificationRequest,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    app: Application = Depends(get_current_application),
    db: AsyncSession = Depends(get_db),
):
    """Unified dispatch endpoint supporting both Telegram and Gmail providers."""
    idempotency_key = x_idempotency_key or payload.idempotency_key
    service = NotificationService(db)

    notification = await service.dispatch(
        application=app,
        provider_name=payload.provider,
        configuration_id=payload.configuration_id,
        payload=payload.payload,
        idempotency_key=idempotency_key,
    )
    return APIResponse(data=NotificationResponse.model_validate(notification))


@router.get(
    "/{notification_id}",
    response_model=APIResponse[NotificationDetailResponse],
    summary="Get notification status and delivery attempts",
)
async def get_notification_status(
    notification_id: uuid.UUID,
    app: Application = Depends(get_current_application),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves delivery status and detailed retry attempts for a notification."""
    service = NotificationService(db)
    notification = await service.get_notification(notification_id, app.id)
    return APIResponse(data=NotificationDetailResponse.model_validate(notification))


@router.get(
    "",
    response_model=APIResponse[list[NotificationResponse]],
    summary="List application notifications",
)
async def list_notifications(
    offset: int = 0,
    limit: int = 50,
    app: Application = Depends(get_current_application),
    db: AsyncSession = Depends(get_db),
):
    """Lists notifications sent by the calling application."""
    service = NotificationService(db)
    notifications = await service.list_notifications(app.id, offset=offset, limit=limit)
    return APIResponse(data=[NotificationResponse.model_validate(n) for n in notifications])

