"""Pydantic schemas for Inbound Messages (Telegram Webhooks & Email Ingestion)."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class InboundMessageResponse(BaseModel):
    """Schema for retrieved incoming messages."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID | None = None
    provider: str
    configuration_id: uuid.UUID | None = None
    sender_identifier: str
    sender_name: str | None = None
    recipient_identifier: str | None = None
    subject: str | None = None
    message_text: str | None = None
    status: str
    created_at: datetime


class TelegramWebhookPayload(BaseModel):
    """Generic payload schema for Telegram Webhook updates."""
    update_id: int
    message: dict | None = None
    channel_post: dict | None = None
    edited_message: dict | None = None


class EmailInboundPayload(BaseModel):
    """Schema for direct incoming email webhook."""
    from_email: str
    from_name: str | None = None
    to_email: str
    subject: str | None = None
    body_text: str | None = None
    raw_payload: str | None = None
