"""Security utilities: API Key generation, HMAC-SHA256 peppered hashing, and verification."""

import hashlib
import hmac
import secrets
from app.core.config import settings


API_KEY_LIVE_PREFIX = "ng_live_"


def generate_api_key() -> tuple[str, str, str]:
    """Generates a secure, cryptographically random API Key.

    Returns:
        (raw_api_key, key_prefix, hashed_key)
        - raw_api_key: Full key shown ONLY once to user (e.g. ng_live_a1b2c3d4_89f...2d)
        - key_prefix: Public lookup index (e.g. ng_live_a1b2c3d4)
        - hashed_key: HMAC-SHA256 hash using the secret pepper
    """
    prefix_id = secrets.token_hex(4)  # 8 hex chars
    secret_part = secrets.token_urlsafe(32)  # high entropy token

    key_prefix = f"{API_KEY_LIVE_PREFIX}{prefix_id}"
    raw_api_key = f"{key_prefix}_{secret_part}"
    hashed_key = hash_api_key_secret(secret_part)

    return raw_api_key, key_prefix, hashed_key


def hash_api_key_secret(secret_part: str, pepper: str | None = None) -> str:
    """Computes HMAC-SHA256 hash of the secret portion using the secret pepper."""
    active_pepper = (pepper or settings.API_KEY_PEPPER).encode("utf-8")
    return hmac.new(active_pepper, secret_part.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_api_key_secret(secret_part: str, expected_hash: str, pepper: str | None = None) -> bool:
    """Verifies secret part against stored hash in constant time to prevent timing attacks."""
    calculated_hash = hash_api_key_secret(secret_part, pepper=pepper)
    return hmac.compare_digest(calculated_hash, expected_hash)


def parse_raw_api_key(raw_key: str) -> tuple[str, str] | None:
    """Splits a raw API key into (key_prefix, secret_part).

    Expected format: ng_live_<prefix_id>_<secret_part>
    """
    if not raw_key or not raw_key.startswith(API_KEY_LIVE_PREFIX):
        return None

    # Strip prefix to find parts
    # Format: ng_live_{8chars}_{secret}
    rest = raw_key[len(API_KEY_LIVE_PREFIX):]
    parts = rest.split("_", 1)
    if len(parts) != 2:
        return None

    prefix_id, secret_part = parts
    key_prefix = f"{API_KEY_LIVE_PREFIX}{prefix_id}"
    return key_prefix, secret_part


def verify_admin_master_key(provided_key: str) -> bool:
    """Verifies if the provided key matches the configured bootstrap ADMIN_API_KEY."""
    if not provided_key or not settings.ADMIN_API_KEY:
        return False
    return hmac.compare_digest(provided_key, settings.ADMIN_API_KEY)
