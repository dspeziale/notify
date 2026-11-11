"""Unit tests for Gmail OAuth and email dispatch provider."""

import base64
from datetime import datetime, timedelta, timezone
import json
import pytest
import httpx
from app.providers.gmail import GmailProvider


@pytest.mark.asyncio
async def test_gmail_send_with_valid_token():
    def mock_handler(request: httpx.Request):
        if request.url.path == "/gmail/v1/users/me/messages/send":
            assert "Authorization" in request.headers
            assert request.headers["Authorization"] == "Bearer VALID_ACCESS_TOKEN"
            data = json.loads(request.content)
            assert "raw" in data
            return httpx.Response(
                status_code=200,
                json={"id": "msg_gmail_12345", "threadId": "thread_123"},
                headers={"content-type": "application/json"},
            )
        return httpx.Response(status_code=404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GmailProvider(
            email_address="sender@example.com",
            client_id="dummy_client_id",
            client_secret="dummy_client_secret",
            refresh_token="dummy_refresh_token",
            access_token="VALID_ACCESS_TOKEN",
            token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
            client=client,
        )

        result = await provider.send({
            "to": ["receiver@example.com"],
            "subject": "Test Subject",
            "text": "Hello plain",
            "html": "<p>Hello HTML</p>",
            "attachments": [
                {
                    "filename": "test.txt",
                    "content_base64": base64.b64encode(b"Attachment data").decode(),
                    "content_type": "text/plain",
                }
            ],
        })

        assert result.success is True
        assert result.provider_message_id == "msg_gmail_12345"
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_gmail_auto_token_refresh():
    refresh_called = False

    def mock_handler(request: httpx.Request):
        nonlocal refresh_called
        if request.url.path == "/token":
            refresh_called = True
            return httpx.Response(
                status_code=200,
                json={
                    "access_token": "NEW_REFRESHED_TOKEN",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
                headers={"content-type": "application/json"},
            )
        elif request.url.path == "/gmail/v1/users/me/messages/send":
            assert request.headers["Authorization"] == "Bearer NEW_REFRESHED_TOKEN"
            return httpx.Response(
                status_code=200,
                json={"id": "msg_after_refresh"},
                headers={"content-type": "application/json"},
            )
        return httpx.Response(status_code=404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # Expired token
        provider = GmailProvider(
            email_address="sender@example.com",
            client_id="dummy_client_id",
            client_secret="dummy_client_secret",
            refresh_token="valid_refresh_token",
            access_token="EXPIRED_TOKEN",
            token_expiry=datetime.now(timezone.utc) - timedelta(minutes=10),
            client=client,
        )

        result = await provider.send({
            "to": ["receiver@example.com"],
            "subject": "After refresh",
            "text": "Content",
        })

        assert refresh_called is True
        assert result.success is True
        assert result.provider_message_id == "msg_after_refresh"
        assert result.new_tokens is not None
        assert result.new_tokens["access_token"] == "NEW_REFRESHED_TOKEN"


@pytest.mark.asyncio
async def test_gmail_send_with_app_password(mocker):
    # Mock aiosmtplib.send
    mock_send = mocker.patch("aiosmtplib.send", mocker.AsyncMock())
    mock_send.return_value = (250, "OK: message queued")

    provider = GmailProvider(
        email_address="app_sender@gmail.com",
        auth_type="app_password",
        app_password="abcd efgh ijkl mnop",  # with spaces, will be trimmed
        smtp_host="smtp.gmail.com",
        smtp_port=587,
    )

    result = await provider.send({
        "to": ["app_receiver@gmail.com"],
        "subject": "App Password Test",
        "text": "Sent via Google App Password",
    })

    assert result.success is True
    assert mock_send.call_count == 1
    # Verify password spaces were stripped
    assert provider.app_password == "abcdefghijklmnop"

