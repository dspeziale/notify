"""Central notification orchestration service with retry, backoff, jitter, and idempotency."""

import asyncio
import logging
import random
import time
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    RateLimitExceededException,
)
from app.core.logging import redact_sensitive_text
from app.core.rate_limiter import rate_limiter
from app.models.application import Application
from app.models.notification import Notification
from app.providers.base import BaseNotificationProvider, ProviderResult
from app.providers.gmail import GmailProvider
from app.providers.telegram import TelegramProvider
from app.repositories.notification_repo import NotificationRepository
from app.services.auth_service import AuthService
from app.services.gmail_config_service import GmailConfigService
from app.services.telegram_config_service import TelegramConfigService

logger = logging.getLogger(__name__)


class NotificationService:
    """Orchestrates notification dispatch, idempotency, retry policies, and tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.notification_repo = NotificationRepository(session)
        self.auth_service = AuthService(session)
        self.telegram_service = TelegramConfigService(session)
        self.gmail_service = GmailConfigService(session)

    async def dispatch(
        self,
        application: Application,
        provider_name: str,
        configuration_id: uuid.UUID,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        custom_provider: BaseNotificationProvider | None = None,
    ) -> Notification:
        """Dispatches a notification respecting rate limits, permissions, and idempotency."""
        # 1. Rate Limiting Check
        allowed, retry_after = await rate_limiter.check_rate_limit(
            str(application.id), application.rate_limit_per_minute
        )
        if not allowed:
            raise RateLimitExceededException(
                f"Rate limit of {application.rate_limit_per_minute} req/min exceeded for {application.name}",
                retry_after=retry_after,
            )

        # 2. Permission Check
        canonical_provider = "gmail" if provider_name == "email" else provider_name
        required_perm = f"{canonical_provider}:send"
        await self.auth_service.verify_permission(application.id, required_perm)

        # 3. Idempotency Check
        if idempotency_key:
            existing = await self.notification_repo.get_by_idempotency_key(
                application.id, idempotency_key
            )
            if existing:
                logger.info(
                    "Idempotency hit for app %s key %s: returning status %s",
                    application.id,
                    idempotency_key,
                    existing.status,
                )
                return existing

        # 4. Resolve and validate configuration (Strict multi-tenant isolation)
        recipient_summary, subject = self._extract_summary(provider_name, payload)

        # 5. Create initial notification record (status='processing')
        notification = Notification(
            application_id=application.id,
            provider=provider_name,
            configuration_id=configuration_id,
            idempotency_key=idempotency_key,
            status="processing",
            recipient_summary=recipient_summary,
            subject=subject,
            attempts_count=0,
        )
        await self.notification_repo.add(notification)

        # 6. Initialize Provider
        provider = custom_provider
        gmail_config = None
        if not provider:
            if provider_name == "telegram":
                tg_config = await self.telegram_service.get_config(
                    configuration_id, app_id=application.id
                )
                if not tg_config.is_active:
                    raise ForbiddenException("Telegram configuration is disabled")
                bot_token = await self.telegram_service.get_decrypted_token(tg_config)
                # Fallback to default_chat_id if not present in payload
                if not payload.get("chat_id") and tg_config.default_chat_id:
                    payload["chat_id"] = tg_config.default_chat_id
                provider = TelegramProvider(bot_token=bot_token)

            elif provider_name == "email":
                gmail_config = await self.gmail_service.get_config(
                    configuration_id, app_id=application.id
                )
                if not gmail_config.is_active:
                    raise ForbiddenException("Gmail configuration is disabled")
                creds = await self.gmail_service.get_decrypted_credentials(gmail_config)
                provider = GmailProvider(
                    email_address=str(creds["email_address"]),
                    auth_type=creds.get("auth_type", "app_password"),
                    app_password=creds.get("app_password"),
                    smtp_host=creds.get("smtp_host", "smtp.gmail.com"),
                    smtp_port=creds.get("smtp_port", 587),
                    client_id=creds.get("client_id"),
                    client_secret=creds.get("client_secret"),
                    refresh_token=creds.get("refresh_token"),
                    access_token=creds.get("access_token"),
                    token_expiry=creds.get("token_expiry"),
                )
            else:
                raise NotFoundException(f"Unsupported notification provider '{provider_name}'")

        # 7. Execute Delivery Loop with Retries, Exponential Backoff and Jitter
        notification = await self._execute_delivery_loop(
            notification=notification,
            provider=provider,
            payload=payload,
            gmail_config=gmail_config,
        )

        return notification

    async def _execute_delivery_loop(
        self,
        notification: Notification,
        provider: BaseNotificationProvider,
        payload: dict[str, Any],
        gmail_config: Any = None,
    ) -> Notification:
        """Executes notification delivery with exponential backoff and jitter."""
        max_retries = settings.NOTIFICATION_MAX_RETRIES
        backoff_factor = settings.NOTIFICATION_RETRY_BACKOFF_FACTOR
        attempt_number = 0
        last_result: ProviderResult | None = None

        while attempt_number <= max_retries:
            attempt_number += 1
            start_time = time.perf_counter()

            result = await provider.send(payload)
            last_result = result
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Persist refreshed tokens if applicable
            if result.new_tokens and gmail_config:
                await self.gmail_service.update_refreshed_tokens(gmail_config, result.new_tokens)

            # Record attempt
            sanitized_err = redact_sensitive_text(result.error_message) if result.error_message else None
            await self.notification_repo.add_attempt(
                notification_id=notification.id,
                attempt_number=attempt_number,
                status="success" if result.success else "failed",
                response_code=result.status_code,
                duration_ms=duration_ms,
                error_message=sanitized_err,
            )

            if result.success:
                # Mark sent
                return await self.notification_repo.update_status(
                    notification=notification,
                    status="sent",
                    attempts_count=attempt_number,
                )

            # If not transient, do not retry
            if not result.is_transient:
                logger.info(
                    "Non-transient error from provider %s, aborting retry: %s",
                    notification.provider,
                    result.error_message,
                )
                break

            # If transient and retries remain, wait with exponential backoff + jitter
            if attempt_number <= max_retries:
                base_delay = backoff_factor ** (attempt_number - 1)
                jitter = random.uniform(0.05, 0.3)
                delay = base_delay + jitter
                logger.info(
                    "Transient error on attempt %d for notification %s. Retrying in %.2fs...",
                    attempt_number,
                    notification.id,
                    delay,
                )
                await asyncio.sleep(delay)

        # Retries exhausted or non-transient error: mark failed
        sanitized_final_error = (
            redact_sensitive_text(last_result.error_message)
            if last_result and last_result.error_message
            else "Notification delivery failed"
        )
        error_code = last_result.error_code if last_result else "DELIVERY_FAILED"

        return await self.notification_repo.update_status(
            notification=notification,
            status="failed",
            attempts_count=attempt_number,
            error_code=error_code,
            error_message=sanitized_final_error,
        )

    def _extract_summary(
        self, provider_name: str, payload: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Extracts non-sensitive summary for reporting."""
        if provider_name == "telegram":
            chat_id = payload.get("chat_id", "default")
            return f"telegram:chat_id={chat_id}", None
        elif provider_name == "email":
            recipients = payload.get("to", [])
            recipient_str = ", ".join(recipients[:3])
            if len(recipients) > 3:
                recipient_str += f" (+{len(recipients) - 3} more)"
            subject = payload.get("subject")
            return f"email:to={recipient_str}", subject
        return None, None

    async def get_notification(
        self, notification_id: uuid.UUID, app_id: uuid.UUID
    ) -> Notification:
        """Retrieves a notification guaranteeing tenant isolation."""
        notification = await self.notification_repo.get_by_id_and_app(notification_id, app_id)
        if not notification:
            raise NotFoundException(f"Notification {notification_id} not found")
        return notification

    async def list_notifications(
        self, app_id: uuid.UUID, offset: int = 0, limit: int = 50
    ) -> list[Notification]:
        """Lists notifications for an application in descending order."""
        return list(await self.notification_repo.list_by_app(app_id, offset=offset, limit=limit))

    async def list_all_notifications(
        self,
        app_id: uuid.UUID | None = None,
        provider: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Notification]:
        """Lists all notifications across applications (admin view)."""
        return list(
            await self.notification_repo.list_all(
                app_id=app_id,
                provider=provider,
                status=status,
                offset=offset,
                limit=limit,
            )
        )

    async def get_notification_admin(self, notification_id: uuid.UUID) -> Notification:
        """Retrieves a notification by ID without tenant restriction (admin view)."""
        notification = await self.notification_repo.get_by_id_admin(notification_id)
        if not notification:
            raise NotFoundException(f"Notification {notification_id} not found")
        return notification
