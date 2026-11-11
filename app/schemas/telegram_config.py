"""Pydantic schemas for Telegram configurations."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TelegramConfigCreate(BaseModel):
    """Schema for creating a Telegram bot configuration."""
    application_id: uuid.UUID = Field(..., description="Target client application UUID")
    name: str = Field(..., min_length=2, max_length=100, description="Friendly configuration name")
    bot_token: str = Field(..., min_length=10, description="Telegram Bot Token (e.g. 123456:ABC-DEF...)")
    default_chat_id: str | None = Field(None, max_length=100, description="Default chat or channel ID")
    is_active: bool = True


class TelegramConfigUpdate(BaseModel):
    """Schema for updating a Telegram bot configuration."""
    name: str | None = Field(None, min_length=2, max_length=100)
    bot_token: str | None = Field(None, min_length=10)
    default_chat_id: str | None = Field(None, max_length=100)
    is_active: bool | None = None


class TelegramConfigResponse(BaseModel):
    """Safe Telegram configuration view (never exposes plaintext bot token)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    name: str
    default_chat_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

