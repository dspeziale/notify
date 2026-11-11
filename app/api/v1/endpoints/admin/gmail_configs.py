"""Administrative endpoints for Gmail API OAuth2 configurations."""

import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_client_ip, get_db, require_admin_auth
from app.schemas.common import APIResponse
from app.schemas.gmail_config import (
    GmailConfigCreate,
    GmailConfigResponse,
    GmailConfigUpdate,
    GmailOAuthInitResponse,
)
from app.services.audit_service import AuditService
from app.services.gmail_config_service import GmailConfigService

router = APIRouter(
    prefix="/admin/gmail",
    tags=["Admin - Gmail Configurations"],
)


@router.post(
    "",
    response_model=APIResponse[GmailConfigResponse],
    summary="Create Gmail configuration",
    dependencies=[Depends(require_admin_auth)],
)
async def create_gmail_config(
    payload: GmailConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Registers a new Gmail API OAuth configuration (credentials are encrypted with AES-256-GCM)."""
    service = GmailConfigService(db)
    audit_service = AuditService(db)

    config = await service.create_config(payload)

    await audit_service.log_event(
        actor_type="admin",
        action="gmail_config.create",
        resource_type="gmail_configuration",
        resource_id=str(config.id),
        details={"application_id": str(config.application_id), "email": config.email_address},
        ip_address=get_client_ip(request),
    )

    response_data = GmailConfigResponse.model_validate(config)
    response_data.is_authorized = bool(config.encrypted_app_password or config.encrypted_refresh_token)
    return APIResponse(data=response_data, message="Gmail configuration created successfully")


@router.get(
    "",
    response_model=APIResponse[list[GmailConfigResponse]],
    summary="List Gmail configurations",
    dependencies=[Depends(require_admin_auth)],
)
async def list_gmail_configs(
    application_id: uuid.UUID | None = Query(None, description="Optional filter by client application UUID"),
    offset: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Lists Gmail configurations for an application."""
    service = GmailConfigService(db)
    configs = await service.list_configs(application_id, offset=offset, limit=limit)
    res = []
    for c in configs:
        item = GmailConfigResponse.model_validate(c)
        item.is_authorized = bool(c.encrypted_app_password or c.encrypted_refresh_token)
        res.append(item)
    return APIResponse(data=res)


@router.get(
    "/{config_id}",
    response_model=APIResponse[GmailConfigResponse],
    summary="Get Gmail configuration",
    dependencies=[Depends(require_admin_auth)],
)
async def get_gmail_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves safe Gmail configuration status."""
    service = GmailConfigService(db)
    config = await service.get_config(config_id)
    item = GmailConfigResponse.model_validate(config)
    item.is_authorized = bool(config.encrypted_app_password or config.encrypted_refresh_token)
    return APIResponse(data=item)


@router.patch(
    "/{config_id}",
    response_model=APIResponse[GmailConfigResponse],
    summary="Update Gmail configuration",
    dependencies=[Depends(require_admin_auth)],
)
async def update_gmail_config(
    config_id: uuid.UUID,
    payload: GmailConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Updates Gmail configuration parameters or credentials."""
    service = GmailConfigService(db)
    audit_service = AuditService(db)

    config = await service.update_config(config_id, payload)

    await audit_service.log_event(
        actor_type="admin",
        action="gmail_config.update",
        resource_type="gmail_configuration",
        resource_id=str(config.id),
        details=payload.model_dump(exclude={"client_secret", "app_password"}, exclude_unset=True),
        ip_address=get_client_ip(request),
    )

    item = GmailConfigResponse.model_validate(config)
    item.is_authorized = bool(config.encrypted_app_password or config.encrypted_refresh_token)
    return APIResponse(data=item, message="Gmail configuration updated successfully")


@router.get(
    "/{config_id}/oauth/authorize",
    response_model=APIResponse[GmailOAuthInitResponse],
    summary="Initiate Google OAuth2 flow",
    dependencies=[Depends(require_admin_auth)],
)
async def initiate_gmail_oauth(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generates Google OAuth2 consent URL for the administrator to authorize sending emails."""
    service = GmailConfigService(db)
    auth_url, state = await service.generate_oauth_url(config_id)
    return APIResponse(
        data=GmailOAuthInitResponse(authorization_url=auth_url, state=state),
        message="Authorize this URL in browser to connect your Google account",
    )


@router.get(
    "/oauth/callback",
    response_model=APIResponse[dict],
    summary="Handle Google OAuth2 callback",
)
async def handle_gmail_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter containing config UUID"),
    db: AsyncSession = Depends(get_db),
):
    """Callback endpoint reached by Google OAuth redirect. Exchanges code for refresh and access tokens."""
    service = GmailConfigService(db)
    audit_service = AuditService(db)

    config = await service.handle_oauth_callback(code, state)

    await audit_service.log_event(
        actor_type="admin",
        action="gmail_config.oauth_connected",
        resource_type="gmail_configuration",
        resource_id=str(config.id),
        details={"email": config.email_address},
    )

    return APIResponse(
        data={"configuration_id": str(config.id), "email_address": config.email_address, "status": "connected"},
        message="Gmail OAuth authorization completed successfully!",
    )


@router.post(
    "/{config_id}/test",
    response_model=APIResponse[dict],
    summary="Test Gmail configuration",
    dependencies=[Depends(require_admin_auth)],
)
async def test_gmail_config(
    config_id: uuid.UUID,
    recipient: str = Query(..., description="Target email address for test message"),
    db: AsyncSession = Depends(get_db),
):
    """Sends a sample test email through the authorized Gmail account."""
    service = GmailConfigService(db)
    result = await service.test_configuration(config_id, test_recipient=recipient)
    return APIResponse(data=result, message="Gmail test executed")


@router.delete(
    "/{config_id}",
    response_model=APIResponse[bool],
    summary="Delete Gmail/SMTP configuration",
    dependencies=[Depends(require_admin_auth)],
)
async def delete_gmail_config(
    config_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Permanently deletes a Gmail or SMTP configuration."""
    service = GmailConfigService(db)
    audit_service = AuditService(db)

    config = await service.get_config(config_id)
    name = config.name

    await service.delete_config(config_id)

    await audit_service.log_event(
        actor_type="admin",
        action="gmail_config.delete",
        resource_type="gmail_configuration",
        resource_id=str(config_id),
        details={"name": name},
        ip_address=get_client_ip(request),
    )

    return APIResponse(data=True, message=f"Gmail/SMTP configuration '{name}' deleted successfully")

