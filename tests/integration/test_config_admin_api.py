"""Integration tests for Telegram and Gmail configuration management."""

import pytest


@pytest.mark.asyncio
async def test_telegram_config_management(client, admin_headers, test_app_and_key):
    app_data, _ = test_app_and_key
    app_id = app_data["id"]

    # 1. Create Telegram Config
    payload = {
        "application_id": app_id,
        "name": "Production Bot",
        "bot_token": "123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "default_chat_id": "-1001234567890",
    }
    create_res = await client.post(
        "/api/v1/admin/telegram", json=payload, headers=admin_headers
    )
    assert create_res.status_code == 200
    config_data = create_res.json()["data"]
    config_id = config_data["id"]

    # Verify sensitive bot token is NEVER returned in response
    assert "bot_token" not in config_data
    assert "encrypted_bot_token" not in config_data
    assert config_data["name"] == "Production Bot"

    # 2. List configs by application_id
    list_res = await client.get(
        f"/api/v1/admin/telegram?application_id={app_id}", headers=admin_headers
    )
    assert list_res.status_code == 200
    assert len(list_res.json()["data"]) >= 1

    # 3. Update Config
    update_res = await client.patch(
        f"/api/v1/admin/telegram/{config_id}",
        json={"name": "Updated Bot Name", "default_chat_id": "-100999999999"},
        headers=admin_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["name"] == "Updated Bot Name"


@pytest.mark.asyncio
async def test_gmail_config_management(client, admin_headers, test_app_and_key):
    app_data, _ = test_app_and_key
    app_id = app_data["id"]

    # 1. Create Gmail Config
    payload = {
        "application_id": app_id,
        "name": "Corporate Gmail",
        "email_address": "support@company.com",
        "client_id": "google-client-id-xyz.apps.googleusercontent.com",
        "client_secret": "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",
    }
    create_res = await client.post(
        "/api/v1/admin/gmail", json=payload, headers=admin_headers
    )
    assert create_res.status_code == 200
    config_data = create_res.json()["data"]
    config_id = config_data["id"]

    # Secrets must not be in response
    assert "client_secret" not in config_data
    assert "encrypted_client_secret" not in config_data
    assert config_data["email_address"] == "support@company.com"
    assert config_data["is_authorized"] is False

    # 2. Initiate OAuth flow
    auth_res = await client.get(
        f"/api/v1/admin/gmail/{config_id}/oauth/authorize", headers=admin_headers
    )
    assert auth_res.status_code == 200
    auth_data = auth_res.json()["data"]
    assert "accounts.google.com" in auth_data["authorization_url"]
    assert auth_data["state"] == config_id

