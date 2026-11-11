"""Pydantic schemas for dispatching and tracking notifications."""

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InlineButtonSchema(BaseModel):
    """Telegram inline keyboard button."""
    text: str = Field(..., min_length=1, max_length=64)
    url: str | None = None
    callback_data: str | None = None


class AttachmentSchema(BaseModel):
    """Email attachment specification."""
    filename: str = Field(..., min_length=1, max_length=255)
    content_base64: str = Field(..., description="Base64-encoded attachment content")
    content_type: str = Field("application/octet-stream", max_length=100)


class TelegramNotificationRequest(BaseModel):
    """Direct request to send a Telegram notification."""
    configuration_id: uuid.UUID
    chat_id: str | None = Field(None, description="Target chat or channel ID. If omitted, uses config default.")
    message: str = Field(..., min_length=1, description="Message text")
    parse_mode: Literal["HTML", "MarkdownV2", "Markdown"] | None = Field(
        "HTML", description="Formatting parser mode"
    )
    buttons: list[list[InlineButtonSchema]] | None = Field(
        None, description="2D matrix of inline buttons"
    )
    idempotency_key: str | None = Field(None, max_length=128)


class EmailNotificationRequest(BaseModel):
    """Direct request to send an Email via Gmail API."""
    configuration_id: uuid.UUID
    to: list[EmailStr] = Field(..., min_length=1, description="Primary recipient email addresses")
    cc: list[EmailStr] = Field(default_factory=list)
    bcc: list[EmailStr] = Field(default_factory=list)
    subject: str = Field(..., min_length=1, max_length=255)
    text: str | None = Field(None, description="Plaintext email body")
    html: str | None = Field(None, description="HTML formatted email body")
    attachments: list[AttachmentSchema] = Field(default_factory=list)
    idempotency_key: str | None = Field(None, max_length=128)


class UnifiedNotificationRequest(BaseModel):
    """Unified dispatch request allowing provider selection in the payload."""
    provider: Literal["telegram", "email"]
    configuration_id: uuid.UUID
    idempotency_key: str | None = Field(None, max_length=128)
    payload: dict[str, Any] = Field(..., description="Provider-specific payload (Telegram or Email schema)")


class NotificationAttemptResponse(BaseModel):
    """Delivery attempt details."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attempt_number: int
    status: str
    response_code: int | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime


class NotificationResponse(BaseModel):
    """Summary response returned immediately upon notification dispatch or status query."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    provider: str
    configuration_id: uuid.UUID
    idempotency_key: str | None
    status: str  # pending, processing, sent, failed
    recipient_summary: str | None
    subject: str | None
    attempts_count: int
    error_code: str | None
    sanitized_error_message: str | None
    created_at: datetime
    sent_at: datetime | None


class NotificationDetailResponse(NotificationResponse):
    """Detailed notification view including all retry attempts."""
    attempts: list[NotificationAttemptResponse] = []

