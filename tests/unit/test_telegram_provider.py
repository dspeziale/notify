"""Unit tests for Telegram provider."""

import json
import pytest
import httpx
from app.providers.telegram import TelegramProvider


@pytest.mark.asyncio
async def test_telegram_send_success():
    def mock_handler(request: httpx.Request):
        assert request.url.path == "/botTEST_TOKEN/sendMessage"
        data = json.loads(request.content)
        assert data["chat_id"] == "123456"
        assert data["text"] == "Hello World"
        assert data["parse_mode"] == "HTML"
        assert "reply_markup" in data
        return httpx.Response(
            status_code=200,
            json={"ok": True, "result": {"message_id": 9988}},
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TelegramProvider(bot_token="TEST_TOKEN", client=client)
        result = await provider.send({
            "chat_id": "123456",
            "message": "Hello World",
            "parse_mode": "HTML",
            "buttons": [[{"text": "Docs", "url": "https://example.com"}]],
        })

        assert result.success is True
        assert result.provider_message_id == "9988"
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_telegram_rate_limit_transient_error():
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            status_code=429,
            json={"ok": False, "description": "Too Many Requests: retry after 5"},
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TelegramProvider(bot_token="TEST_TOKEN", client=client)
        result = await provider.send({
            "chat_id": "123456",
            "message": "Spamming",
        })

        assert result.success is False
        assert result.is_transient is True
        assert result.status_code == 429
        assert "Too Many Requests" in result.error_message


@pytest.mark.asyncio
async def test_telegram_invalid_payload():
    provider = TelegramProvider(bot_token="TEST_TOKEN")
    result = await provider.send({})
    assert result.success is False
    assert result.error_code == "INVALID_PAYLOAD"
    assert result.is_transient is False

