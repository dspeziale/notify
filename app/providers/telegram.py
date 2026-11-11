"""Telegram Bot API notification provider."""

import logging
from typing import Any
import httpx
from app.core.config import settings
from app.providers.base import BaseNotificationProvider, ProviderResult

logger = logging.getLogger(__name__)


class TelegramProvider(BaseNotificationProvider):
    """Integrates with Telegram Bot API sendMessage endpoint."""

    BASE_URL = "https://api.telegram.org"

    def __init__(self, bot_token: str, client: httpx.AsyncClient | None = None):
        self._bot_token = bot_token
        self._client = client

    async def send(self, payload: dict[str, Any]) -> ProviderResult:
        """Sends a message via Telegram Bot API."""
        chat_id = payload.get("chat_id")
        text = payload.get("message")
        parse_mode = payload.get("parse_mode", "HTML")
        buttons = payload.get("buttons")

        if not chat_id or not text:
            return ProviderResult(
                success=False,
                error_code="INVALID_PAYLOAD",
                error_message="chat_id and message are required for Telegram notifications",
                is_transient=False,
            )

        endpoint = f"{self.BASE_URL}/bot{self._bot_token}/sendMessage"

        body: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            body["parse_mode"] = parse_mode

        if buttons:
            inline_keyboard = []
            for row in buttons:
                button_row = []
                for btn in row:
                    item = {"text": btn.get("text")}
                    if btn.get("url"):
                        item["url"] = btn["url"]
                    elif btn.get("callback_data"):
                        item["callback_data"] = btn["callback_data"]
                    button_row.append(item)
                inline_keyboard.append(button_row)
            body["reply_markup"] = {"inline_keyboard": inline_keyboard}

        try:
            if self._client:
                response = await self._client.post(
                    endpoint, json=body, timeout=settings.NOTIFICATION_TIMEOUT_SECONDS
                )
            else:
                async with httpx.AsyncClient(timeout=settings.NOTIFICATION_TIMEOUT_SECONDS) as client:
                    response = await client.post(endpoint, json=body)

            status_code = response.status_code
            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

            if status_code == 200 and data.get("ok"):
                message_id = str(data.get("result", {}).get("message_id"))
                return ProviderResult(
                    success=True,
                    provider_message_id=message_id,
                    status_code=status_code,
                )

            # Failure response
            description = data.get("description", "Unknown Telegram error")
            is_transient = status_code == 429 or status_code >= 500
            error_code = f"TELEGRAM_ERROR_{status_code}"

            logger.warning(
                "Telegram dispatch failed: HTTP %s: %s (transient=%s)",
                status_code,
                description,
                is_transient,
            )

            return ProviderResult(
                success=False,
                status_code=status_code,
                error_code=error_code,
                error_message=description,
                is_transient=is_transient,
            )

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning("Telegram network/timeout exception: %s", exc)
            return ProviderResult(
                success=False,
                error_code="NETWORK_TIMEOUT",
                error_message=f"Network or timeout error contacting Telegram API: {str(exc)}",
                is_transient=True,
            )
        except Exception as exc:
            logger.error("Unexpected Telegram provider exception: %s", exc)
            return ProviderResult(
                success=False,
                error_code="UNEXPECTED_ERROR",
                error_message=f"Unexpected error: {str(exc)}",
                is_transient=False,
            )

