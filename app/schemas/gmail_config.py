"""Pydantic schemas for Gmail / Email configurations with App Passwords & OAuth."""

from typing import Literal
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class GmailConfigCreate(BaseModel):
    """Schema for creating a Gmail / Email integration configuration."""
    application_id: uuid.UUID = Field(..., description="Target client application UUID")
    name: str = Field(..., min_length=2, max_length=100, description="Friendly configuration name")
    email_address: EmailStr = Field(..., description="Google/Gmail account address")

    auth_type: Literal["app_password", "oauth2"] = Field(
        "app_password",
        description="'app_password' for Google App Passwords (SMTP), or 'oauth2' for OAuth flow",
    )

    # For Google App Password (SMTP)
    app_password: str | None = Field(
        None,
        min_length=8,
        description="Google App Password (16-char password generated in Google Security settings)",
    )
    smtp_host: str = Field("smtp.gmail.com", max_length=100)
    smtp_port: int = Field(587, ge=1, le=65535)

    # For OAuth2 (Optional if using app_password)
    client_id: str | None = Field(None, min_length=5, description="Google Cloud OAuth Client ID")
    client_secret: str | None = Field(None, min_length=5, description="Google Cloud OAuth Client Secret")

    is_active: bool = True


class GmailConfigUpdate(BaseModel):
    """Schema for updating a Gmail / Email configuration."""
    name: str | None = Field(None, min_length=2, max_length=100)
    email_address: EmailStr | None = None
    auth_type: Literal["app_password", "oauth2"] | None = None
    app_password: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    client_id: str | None = None
    client_secret: str | None = None
    is_active: bool | None = None


class GmailConfigResponse(BaseModel):
    """Safe Gmail / Email configuration response (passwords and secrets are strictly redacted)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    name: str
    email_address: str
    auth_type: str = "app_password"
    smtp_host: str | None = "smtp.gmail.com"
    smtp_port: int | None = 587
    scopes: str
    is_active: bool
    is_authorized: bool = Field(False, description="Whether App Password or OAuth is connected")
    token_expiry: datetime | None = None
    created_at: datetime
    updated_at: datetime


class GmailOAuthInitResponse(BaseModel):
    """Response containing Google OAuth2 consent URL."""
    authorization_url: str
    state: str
