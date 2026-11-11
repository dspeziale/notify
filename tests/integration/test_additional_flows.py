"""Additional integration tests for Gmail notification, unified endpoint, test triggers, and audit log APIs."""

import base64
from unittest.mock import AsyncMock, patch
import pytest
from app.providers.base import ProviderResult


@pytest.mark.asyncio
async def test_email_dispatch_and_unified_endpoint(client, admin_headers, test_app_and_key):
    app_data, raw_key = test_app_and_key
    app_id = app_data["id"]

    # 1. Create Gmail Configuration
    gmail_res = await client.post(
        "/api/v1/admin/gmail",
        json={
            "application_id": app_id,
            "name": "Billing Mailer",
            "email_address": "billing@example.com",
            "client_id": "oauth-client-id",
            "client_secret": "oauth-client-secret",
        },
        headers=admin_headers,
    )
    config_id = gmail_res.json()["data"]["id"]

    mock_send = AsyncMock(
        return_value=ProviderResult(
            success=True,
            provider_message_id="gmail_msg_8877",
            status_code=200,
        )
    )

    # 2. Test direct POST /api/v1/notifications/email
    with patch("app.services.notification_service.GmailProvider.send", mock_send):
        email_res = await client.post(
            "/api/v1/notifications/email",
            json={
                "configuration_id": config_id,
                "to": ["client@example.com"],
                "subject": "Invoice #1024",
                "text": "Your invoice is ready.",
                "html": "<p>Your invoice is ready.</p>",
                "attachments": [
                    {
                        "filename": "invoice.pdf",
                        "content_base64": base64.b64encode(b"%PDF-1.4 dummy pdf bytes").decode(),
                        "content_type": "application/pdf",
                    }
                ],
            },
            headers={"X-API-Key": raw_key},
        )
        assert email_res.status_code == 200
        assert email_res.json()["data"]["status"] == "sent"

    # 3. Test unified endpoint POST /api/v1/notifications
    with patch("app.services.notification_service.GmailProvider.send", mock_send):
        unified_res = await client.post(
            "/api/v1/notifications",
            json={
                "provider": "email",
                "configuration_id": config_id,
                "payload": {
                    "to": ["partner@example.com"],
                    "subject": "Unified Alert",
                    "text": "Unified content",
                },
            },
            headers={"X-API-Key": raw_key},
        )
        assert unified_res.status_code == 200
        assert unified_res.json()["data"]["status"] == "sent"


@pytest.mark.asyncio
async def test_audit_logs_and_test_endpoints(client, admin_headers, test_app_and_key):
    app_data, raw_key = test_app_and_key
    app_id = app_data["id"]

    # Create telegram config
    tg_res = await client.post(
        "/api/v1/admin/telegram",
        json={
            "application_id": app_id,
            "name": "Bot To Test",
            "bot_token": "123456789:VALID_TOKEN",
            "default_chat_id": "12345",
        },
        headers=admin_headers,
    )
    tg_config_id = tg_res.json()["data"]["id"]

    # Test Telegram configuration endpoint
    with patch("app.services.telegram_config_service.TelegramProvider.send", AsyncMock(return_value=ProviderResult(success=True, provider_message_id="111"))):
        test_tg_res = await client.post(
            f"/api/v1/admin/telegram/{tg_config_id}/test",
            headers=admin_headers,
        )
        assert test_tg_res.status_code == 200
        assert test_tg_res.json()["data"]["success"] is True

    # Check Audit Logs
    audit_res = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()["data"]
    assert len(logs) > 0
    actions = [log["action"] for log in logs]
    assert "telegram_config.create" in actions
