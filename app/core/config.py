"""Centralized configuration management using Pydantic Settings."""

import json
from typing import Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "VORTEX - Versatile Omnichannel Routing & Telegram-Email eXchange"
    PROJECT_ACRONYM: str = "VORTEX"
    PROJECT_SUBTITLE: str = "Versatile Omnichannel Routing & Telegram-Email eXchange"
    VERSION: str = "0.6.6"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./notification_gateway.db"

    # Redis
    REDIS_URL: str | None = None
    REDIS_ENABLED: bool = False

    # Security & Encryption (AES-256-GCM)
    # Master key is 32 bytes URL-safe base64 encoded string
    # Default provided for immediate out-of-the-box development, must be overridden in production
    MASTER_ENCRYPTION_KEY: str = "k5b1A0r_y8qR_hN7YJbM5x6_Z8V3qL2kM4p1R9s8T2A="
    ACTIVE_KEY_VERSION: str = "v1"
    # Additional keys for rotation in format: {"v1": "key1", "v2": "key2"} or JSON string
    KEY_ROTATION_RING: str = "{}"

    # API Key Hashing Pepper (secret key used in HMAC-SHA256)
    API_KEY_PEPPER: str = "super-secret-pepper-change-in-production-12345678"

    # Bootstrap Admin API Key
    ADMIN_API_KEY: str = "admin-secret-key-change-in-production-abcdef123456"

    # Rate Limiting
    DEFAULT_RATE_LIMIT_PER_MINUTE: int = 60

    # Notification Policies
    NOTIFICATION_MAX_RETRIES: int = 3
    NOTIFICATION_RETRY_BACKOFF_FACTOR: float = 1.5
    NOTIFICATION_TIMEOUT_SECONDS: float = 15.0
    MAX_ATTACHMENT_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Google OAuth
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/admin/gmail/oauth/callback"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    def get_key_ring(self) -> dict[str, str]:
        """Returns the dictionary mapping version tag -> base64 32-byte key."""
        keys = {self.ACTIVE_KEY_VERSION: self.MASTER_ENCRYPTION_KEY}
        if self.KEY_ROTATION_RING:
            try:
                parsed = json.loads(self.KEY_ROTATION_RING)
                if isinstance(parsed, dict):
                    keys.update(parsed)
            except Exception:
                pass
        return keys


settings = Settings()
