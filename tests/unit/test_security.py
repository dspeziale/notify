"""Unit tests for API key generation, parsing, hashing, and verification."""

import pytest
from app.core.security import (
    generate_api_key,
    parse_raw_api_key,
    hash_api_key_secret,
    verify_api_key_secret,
    verify_admin_master_key,
)
from app.core.rate_limiter import rate_limiter


def test_api_key_generation_and_verification():
    raw_key, key_prefix, hashed_key = generate_api_key()

    assert raw_key.startswith("ng_live_")
    assert key_prefix.startswith("ng_live_")
    assert key_prefix in raw_key
    assert len(hashed_key) == 64  # sha256 hex length

    parsed = parse_raw_api_key(raw_key)
    assert parsed is not None
    parsed_prefix, secret_part = parsed
    assert parsed_prefix == key_prefix

    # Verify matching secret
    assert verify_api_key_secret(secret_part, hashed_key) is True
    # Tampered secret must fail
    assert verify_api_key_secret(secret_part + "tamper", hashed_key) is False


def test_invalid_api_key_parsing():
    assert parse_raw_api_key("invalid_prefix_123") is None
    assert parse_raw_api_key("") is None
    assert parse_raw_api_key("ng_live_incomplete") is None


def test_admin_master_key():
    from app.core.config import settings
    assert verify_admin_master_key(settings.ADMIN_API_KEY) is True
    assert verify_admin_master_key("wrong-key") is False
    assert verify_admin_master_key("") is False


@pytest.mark.asyncio
async def test_rate_limiter_in_memory():
    app_id = "test-app-123"
    rate_limiter.reset_in_memory(app_id)

    # Allow 3 requests per minute
    allowed1, _ = await rate_limiter.check_rate_limit(app_id, 3)
    allowed2, _ = await rate_limiter.check_rate_limit(app_id, 3)
    allowed3, _ = await rate_limiter.check_rate_limit(app_id, 3)
    allowed4, retry_after = await rate_limiter.check_rate_limit(app_id, 3)

    assert allowed1 is True
    assert allowed2 is True
    assert allowed3 is True
    assert allowed4 is False
    assert retry_after > 0
