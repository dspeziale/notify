"""Integration tests for idempotency keys and retry backoff mechanics."""

from unittest.mock import AsyncMock, patch
import pytest
from app.providers.base import ProviderResult


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_sends(client, admin_headers, test_app_and_key):
    app_data, raw_key = test_app_and_key
    app_id = app_data["id"]

    tg_config_res = await client.post(
        "/api/v1/admin/telegram",
        json={
            "application_id": app_id,
            "name": "Idempotent Bot",
            "bot_token": "123456:BOT",
            "default_chat_id": "999",
        },
        headers=admin_headers,
    )
    config_id = tg_config_res.json()["data"]["id"]

    mock_send = AsyncMock(
        return_value=ProviderResult(
            success=True,
            provider_message_id="msg_first_call",
            status_code=200,
        )
    )

    with patch("app.services.notification_service.TelegramProvider.send", mock_send):
        payload = {
            "configuration_id": config_id,
            "chat_id": "999",
            "message": "Payment Confirmation",
            "idempotency_key": "payment_order_tx_98765",
        }

        # First request
        res1 = await client.post(
            "/api/v1/notifications/telegram",
            json=payload,
            headers={"X-API-Key": raw_key},
        )
        assert res1.status_code == 200
        notif_id_1 = res1.json()["data"]["id"]
        assert mock_send.call_count == 1

        # Second request with SAME idempotency key
        res2 = await client.post(
            "/api/v1/notifications/telegram",
            json=payload,
            headers={"X-API-Key": raw_key},
        )
        assert res2.status_code == 200
        notif_id_2 = res2.json()["data"]["id"]

        # Must return the identical notification ID without re-invoking the provider
        assert notif_id_1 == notif_id_2
        assert mock_send.call_count == 1


@pytest.mark.asyncio
async def test_retry_on_transient_error(client, admin_headers, test_app_and_key):
    app_data, raw_key = test_app_and_key
    app_id = app_data["id"]

    tg_config_res = await client.post(
        "/api/v1/admin/telegram",
        json={
            "application_id": app_id,
            "name": "Retry Bot",
            "bot_token": "123456:BOT",
            "default_chat_id": "888",
        },
        headers=admin_headers,
    )
    config_id = tg_config_res.json()["data"]["id"]

    # First attempt: transient 429
    # Second attempt: success
    side_effects = [
        ProviderResult(
            success=False,
            status_code=429,
            error_code="RATE_LIMIT",
            error_message="Too Many Requests",
            is_transient=True,
        ),
        ProviderResult(
            success=True,
            provider_message_id="msg_success_retry",
            status_code=200,
        ),
    ]

    mock_send = AsyncMock(side_effect=side_effects)

    with patch("app.services.notification_service.TelegramProvider.send", mock_send):
        with patch("asyncio.sleep", AsyncMock()):  # Skip sleep duration in test
            res = await client.post(
                "/api/v1/notifications/telegram",
                json={
                    "configuration_id": config_id,
                    "chat_id": "888",
                    "message": "Message requiring retry",
                },
                headers={"X-API-Key": raw_key},
            )

            assert res.status_code == 200
            data = res.json()["data"]
            assert data["status"] == "sent"
            assert data["attempts_count"] == 2
            assert mock_send.call_count == 2

