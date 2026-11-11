"""Authentication and authorization service for client applications and admins."""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AuthenticationException, ForbiddenException
from app.core.security import (
    parse_raw_api_key,
    verify_admin_master_key,
    verify_api_key_secret,
)
from app.models.api_key import APIKey
from app.models.application import Application
from app.repositories.api_key_repo import APIKeyRepository
from app.repositories.application_repo import ApplicationRepository


class AuthService:
    """Manages authentication validation and permission checks."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.api_key_repo = APIKeyRepository(session)
        self.app_repo = ApplicationRepository(session)

    async def authenticate_application(self, raw_api_key: str) -> Application:
        """Authenticates a client application via raw API Key.

        Validates:
        1. Correct format (ng_live_<prefix>_<secret>)
        2. Prefix match in database
        3. Constant-time HMAC-SHA256 verification
        4. Key active and unexpired
        5. Application active
        """
        parsed = parse_raw_api_key(raw_api_key)
        if not parsed:
            raise AuthenticationException("Invalid API key format")

        key_prefix, secret_part = parsed
        api_key_record = await self.api_key_repo.get_by_prefix(key_prefix)
        if not api_key_record:
            raise AuthenticationException("Invalid API key")

        if not verify_api_key_secret(secret_part, api_key_record.hashed_key):
            raise AuthenticationException("Invalid API key")

        if not api_key_record.is_valid:
            raise AuthenticationException("API key has been revoked or expired")

        app = api_key_record.application
        if not app:
            raise AuthenticationException("API key is not associated with an active application")

        if not app.is_active:
            raise ForbiddenException("Client application has been disabled. Contact administrator.")

        return app

    async def verify_permission(self, application_id: uuid.UUID, required_permission: str) -> None:
        """Verifies that an application holds the requested permission."""
        app = await self.app_repo.get_by_id_with_relations(application_id)
        if not app:
            raise ForbiddenException("Application not found")

        active_permissions = {p.permission for p in app.permissions}
        if required_permission not in active_permissions:
            raise ForbiddenException(
                f"Application lacks required permission '{required_permission}'"
            )

    async def authenticate_admin(self, raw_key: str) -> bool:
        """Validates admin access against master key or database admin keys."""
        # 1. Check bootstrap master admin key
        if verify_admin_master_key(raw_key):
            return True

        # 2. Check database admin API keys
        parsed = parse_raw_api_key(raw_key)
        if parsed:
            key_prefix, secret_part = parsed
            key_record = await self.api_key_repo.get_by_prefix(key_prefix)
            if key_record and key_record.is_admin and key_record.is_valid:
                if verify_api_key_secret(secret_part, key_record.hashed_key):
                    return True

        raise AuthenticationException("Invalid administrator credentials")

