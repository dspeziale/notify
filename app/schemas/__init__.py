"""Schemas package exports."""

from app.schemas.common import APIResponse, ErrorDetail, ErrorResponse
from app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationDetailResponse,
    APIKeyCreate,
    APIKeyResponse,
)
from app.schemas.telegram_config import (
    TelegramConfigCreate,
    TelegramConfigUpdate,
    TelegramConfigResponse,
)
from app.schemas.gmail_config import (
    GmailConfigCreate,
    GmailConfigUpdate,
    GmailConfigResponse,
    GmailOAuthInitResponse,
)
from app.schemas.notification import (
    TelegramNotificationRequest,
    EmailNotificationRequest,
    UnifiedNotificationRequest,
    NotificationResponse,
    NotificationDetailResponse,
    NotificationAttemptResponse,
    InlineButtonSchema,
    AttachmentSchema,
)
from app.schemas.audit_log import AuditLogResponse

__all__ = [
    "APIResponse",
    "ErrorDetail",
    "ErrorResponse",
    "ApplicationCreate",
    "ApplicationUpdate",
    "ApplicationResponse",
    "ApplicationDetailResponse",
    "APIKeyCreate",
    "APIKeyResponse",
    "TelegramConfigCreate",
    "TelegramConfigUpdate",
    "TelegramConfigResponse",
    "GmailConfigCreate",
    "GmailConfigUpdate",
    "GmailConfigResponse",
    "GmailOAuthInitResponse",
    "TelegramNotificationRequest",
    "EmailNotificationRequest",
    "UnifiedNotificationRequest",
    "NotificationResponse",
    "NotificationDetailResponse",
    "NotificationAttemptResponse",
    "InlineButtonSchema",
    "AttachmentSchema",
    "AuditLogResponse",
]

