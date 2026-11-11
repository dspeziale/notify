"""Integration tests for notification dispatching, permissions, and tenant isolation."""

from unittest.mock import AsyncMock, patch
import pytest
from app.providers.base import ProviderResult


@pytest.mark.asyncio
async def test_telegram_dispatch_flow(client, admin_headers, test_app_and_key):
    app_data, raw_key = test_app_and_key
    app_id = app_data["id"]

    # 1. Create a Telegram configuration for this app
    tg_config_res = await client.post(
        "/api/v1/admin/telegram",
        json={
            "application_id": app_id,
            "name": "Alerts Bot",
            "bot_token": "123456:FAKE-BOT-TOKEN",
            "default_chat_id": "12345678",
        },
        headers=admin_headers,
    )
    config_id = tg_config_res.json()["data"]["id"]

    # Mock TelegramProvider.send to succeed
    mock_send = AsyncMock(
        return_value=ProviderResult(
            success=True,
            provider_message_id="msg_tg_999",
            status_code=200,
        )
    )

    with patch("app.services.notification_service.TelegramProvider.send", mock_send):
        res = await client.post(
            "/api/v1/notifications/telegram",
            json={
                "configuration_id": config_id,
                "chat_id": "12345678",
                "message": "Critical Server Alert",
                "parse_mode": "HTML",
            },
            headers={"X-API-Key": raw_key},
        )

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["status"] == "sent"
        assert data["attempts_count"] == 1
        notif_id = data["id"]

        # Check status endpoint
        status_res = await client.get(
            f"/api/v1/notifications/{notif_id}",
            headers={"X-API-Key": raw_key},
        )
        assert status_res.status_code == 200
        detail = status_res.json()["data"]
        assert detail["status"] == "sent"
        assert len(detail["attempts"]) == 1
        assert detail["attempts"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_tenant_isolation_cross_application_access(client, admin_headers, test_app_and_key):
    """Ensures Application A cannot use Application B's configuration."""
    app_a, key_a = test_app_and_key

    # Create Application B
    app_b_res = await client.post(
        "/api/v1/admin/applications",
        json={"name": "Application B", "permissions": ["telegram:send"]},
        headers=admin_headers,
    )
    key_b = app_b_res.json()["data"]["initial_api_key"]["raw_api_key"]

    # Create Telegram config belonging strictly to Application A
    config_a_res = await client.post(
        "/api/v1/admin/telegram",
        json={
            "application_id": app_a["id"],
            "name": "App A Secret Bot",
            "bot_token": "123456:TOKEN_A",
            "default_chat_id": "111",
        },
        headers=admin_headers,
    )
    config_a_id = config_a_res.json()["data"]["id"]

    # Application B tries to use Config A -> Must return 404
    hack_res = await client.post(
        "/api/v1/notifications/telegram",
        json={
            "configuration_id": config_a_id,
            "message": "Attempting cross-tenant notification",
        },
        headers={"X-API-Key": key_b},
    )
    assert hack_res.status_code == 404
    assert hack_res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_permission_denial(client, admin_headers):
    """Ensures application without gmail:send permission cannot send emails."""
    # App with ONLY telegram:send
    app_res = await client.post(
        "/api/v1/admin/applications",
        json={"name": "Telegram Only App", "permissions": ["telegram:send"]},
        headers=admin_headers,
    )
    key = app_res.json()["data"]["initial_api_key"]["raw_api_key"]

    email_res = await client.post(
        "/api/v1/notifications/email",
        json={
            "configuration_id": "00000000-0000-0000-0000-000000000000",
            "to": ["user@example.com"],
            "subject": "Forbidden Email",
            "text": "Forbidden",
        },
        headers={"X-API-Key": key},
    )
    assert email_res.status_code == 403
    assert email_res.json()["error"]["code"] == "PERMISSION_DENIED"

