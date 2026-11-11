"""Pydantic schemas for Client Applications and API Keys."""

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationCreate(BaseModel):
    """Schema for registering a new client application."""
    name: str = Field(..., min_length=2, max_length=100, description="Unique client application name")
    description: str | None = Field(None, max_length=500)
    rate_limit_per_minute: int = Field(60, ge=1, le=10000, description="Requests per minute rate limit")
    permissions: list[str] = Field(
        default_factory=lambda: ["telegram:send", "gmail:send"],
        description="List of allowed permissions (e.g. 'telegram:send', 'gmail:send')",
    )


class ApplicationUpdate(BaseModel):
    """Schema for updating an existing client application."""
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=500)
    status: str | None = Field(None, pattern="^(active|disabled)$")
    rate_limit_per_minute: int | None = Field(None, ge=1, le=10000)
    permissions: list[str] | None = None


class APIKeyCreate(BaseModel):
    """Schema for generating an additional API key for an application."""
    name: str = Field(..., min_length=1, max_length=100, description="Key description/identifier")
    expires_in_days: int | None = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """Public API key view. Note: raw_api_key is only present at generation time."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    raw_api_key: str | None = Field(
        None, description="Cryptographic full API Key. Exposed ONLY ONCE upon creation or regeneration."
    )


class ApplicationResponse(BaseModel):
    """Complete application response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: str
    rate_limit_per_minute: int
    created_at: datetime
    updated_at: datetime
    permissions: list[str] = []
    api_keys: list[APIKeyResponse] = []

    @field_validator("permissions", mode="before")
    @classmethod
    def serialize_permissions(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            result = []
            for item in v:
                if hasattr(item, "permission"):
                    result.append(item.permission)
                elif isinstance(item, str):
                    result.append(item)
            return result
        return []


class ApplicationDetailResponse(ApplicationResponse):
    """Application detail response including initial raw API Key if just created."""
    initial_api_key: APIKeyResponse | None = None
