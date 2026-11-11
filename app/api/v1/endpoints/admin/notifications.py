"""Admin notification management and global tracking endpoints."""

import uuid
from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_admin_auth
from app.schemas.common import APIResponse
from app.schemas.notification import NotificationDetailResponse, NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/admin/notifications", tags=["Admin - Notifications"])


@router.get(
    "",
    response_model=APIResponse[list[NotificationResponse]],
    summary="List all notifications across applications (Admin only)",
)
async def list_all_notifications_admin(
    application_id: uuid.UUID | None = Query(None, description="Filter by Application ID"),
    provider: Literal["telegram", "email"] | None = Query(None, description="Filter by Provider"),
    status: Literal["pending", "processing", "sent", "failed"] | None = Query(
        None, description="Filter by Status"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin_auth: bool = Depends(require_admin_auth),
    db: AsyncSession = Depends(get_db),
):
    """Lists recent notifications across all applications with filtering."""
    service = NotificationService(db)
    notifications = await service.list_all_notifications(
        app_id=application_id,
        provider=provider,
        status=status,
        offset=offset,
        limit=limit,
    )
    return APIResponse(data=[NotificationResponse.model_validate(n) for n in notifications])


@router.get(
    "/{notification_id}",
    response_model=APIResponse[NotificationDetailResponse],
    summary="Get notification detail with attempts (Admin only)",
)
async def get_notification_detail_admin(
    notification_id: uuid.UUID,
    admin_auth: bool = Depends(require_admin_auth),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full details and retry attempts for any notification."""
    service = NotificationService(db)
    notification = await service.get_notification_admin(notification_id)
    return APIResponse(data=NotificationDetailResponse.model_validate(notification))
