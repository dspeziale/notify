"""Administrative endpoints for client applications and API keys."""

import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_client_ip, get_db, require_admin_auth
from app.schemas.application import (
    APIKeyResponse,
    ApplicationCreate,
    ApplicationDetailResponse,
    ApplicationResponse,
    ApplicationUpdate,
)
from app.schemas.common import APIResponse
from app.services.application_service import ApplicationService
from app.services.audit_service import AuditService

router = APIRouter(
    prefix="/admin/applications",
    tags=["Admin - Applications"],
    dependencies=[Depends(require_admin_auth)],
)


@router.post("", response_model=APIResponse[ApplicationDetailResponse], summary="Register new application")
async def create_application(
    payload: ApplicationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Creates a new client application and returns its initial API Key.

    IMPORTANT: The raw_api_key in the response is shown ONLY ONCE!
    """
    app_service = ApplicationService(db)
    audit_service = AuditService(db)

    app, raw_key = await app_service.create_application(payload)

    # Format response
    response_data = ApplicationDetailResponse.model_validate(app)
    response_data.permissions = [p.permission for p in app.permissions]
    if app.api_keys:
        initial_key = APIKeyResponse.model_validate(app.api_keys[0])
        initial_key.raw_api_key = raw_key
        response_data.initial_api_key = initial_key

    await audit_service.log_event(
        actor_type="admin",
        action="application.create",
        resource_type="application",
        resource_id=str(app.id),
        details={"name": app.name, "rate_limit": app.rate_limit_per_minute},
        ip_address=get_client_ip(request),
    )

    return APIResponse(data=response_data, message="Application registered successfully")


@router.get("", response_model=APIResponse[list[ApplicationResponse]], summary="List applications")
async def list_applications(
    offset: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Lists registered client applications."""
    app_service = ApplicationService(db)
    apps = await app_service.list_applications(offset=offset, limit=limit)
    result = []
    for app in apps:
        item = ApplicationResponse.model_validate(app)
        item.permissions = [p.permission for p in app.permissions]
        result.append(item)
    return APIResponse(data=result)


@router.get("/{app_id}", response_model=APIResponse[ApplicationResponse], summary="Get application details")
async def get_application(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full details for a client application."""
    app_service = ApplicationService(db)
    app = await app_service.get_application(app_id)
    item = ApplicationResponse.model_validate(app)
    item.permissions = [p.permission for p in app.permissions]
    return APIResponse(data=item)


@router.patch("/{app_id}", response_model=APIResponse[ApplicationResponse], summary="Update application")
async def update_application(
    app_id: uuid.UUID,
    payload: ApplicationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Updates an application's name, description, status (active/disabled), rate limit, or permissions."""
    app_service = ApplicationService(db)
    audit_service = AuditService(db)

    app = await app_service.update_application(app_id, payload)

    await audit_service.log_event(
        actor_type="admin",
        action="application.update",
        resource_type="application",
        resource_id=str(app.id),
        details=payload.model_dump(exclude_unset=True),
        ip_address=get_client_ip(request),
    )

    item = ApplicationResponse.model_validate(app)
    item.permissions = [p.permission for p in app.permissions]
    return APIResponse(data=item, message="Application updated successfully")


@router.post(
    "/{app_id}/regenerate-key",
    response_model=APIResponse[APIKeyResponse],
    summary="Regenerate application API Key",
)
async def regenerate_api_key(
    app_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Revokes all existing keys for the application and generates a new API Key."""
    app_service = ApplicationService(db)
    audit_service = AuditService(db)

    new_key, raw_key = await app_service.regenerate_api_key(app_id)

    await audit_service.log_event(
        actor_type="admin",
        action="api_key.regenerate",
        resource_type="application",
        resource_id=str(app_id),
        details={"key_id": str(new_key.id), "key_prefix": new_key.key_prefix},
        ip_address=get_client_ip(request),
    )

    result = APIKeyResponse.model_validate(new_key)
    result.raw_api_key = raw_key
    return APIResponse(data=result, message="New API Key generated successfully. Save it now.")


@router.post(
    "/keys/{key_id}/revoke",
    response_model=APIResponse[bool],
    summary="Revoke an API Key",
)
async def revoke_api_key(
    key_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Immediately revokes an active API Key."""
    app_service = ApplicationService(db)
    audit_service = AuditService(db)

    await app_service.revoke_api_key(key_id)

    await audit_service.log_event(
        actor_type="admin",
        action="api_key.revoke",
        resource_type="api_key",
        resource_id=str(key_id),
        ip_address=get_client_ip(request),
    )

    return APIResponse(data=True, message="API Key revoked successfully")


@router.delete(
    "/{app_id}",
    response_model=APIResponse[bool],
    summary="Delete an application and all its configurations",
)
async def delete_application(
    app_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Permanently deletes an application, including its API keys, configs, and notifications."""
    app_service = ApplicationService(db)
    audit_service = AuditService(db)

    app = await app_service.get_application(app_id)
    app_name = app.name

    await app_service.delete_application(app_id)

    await audit_service.log_event(
        actor_type="admin",
        action="application.delete",
        resource_type="application",
        resource_id=str(app_id),
        details={"name": app_name},
        ip_address=get_client_ip(request),
    )

    return APIResponse(data=True, message=f"Application '{app_name}' deleted successfully")

