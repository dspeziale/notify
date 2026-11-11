"""Gmail / Email configuration and authorization management service."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import uuid
from typing import Any, Sequence
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.encryption import encryption_service
from app.core.exceptions import NotFoundException
from app.models.gmail_config import GmailConfiguration
from app.providers.gmail import GmailProvider
from app.repositories.application_repo import ApplicationRepository
from app.repositories.gmail_config_repo import GmailConfigRepository
from app.schemas.gmail_config import GmailConfigCreate, GmailConfigUpdate


class GmailConfigService:
    """Manages Email/Gmail configurations with Google App Passwords and OAuth2."""

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GmailConfigRepository(session)
        self.app_repo = ApplicationRepository(session)

    async def create_config(self, data: GmailConfigCreate) -> GmailConfiguration:
        """Encrypts credentials and registers Email/Gmail configuration."""
        app = await self.app_repo.get_by_id(data.application_id)
        if not app:
            raise NotFoundException(f"Application {data.application_id} not found")

        encrypted_app_password = (
            encryption_service.encrypt(data.app_password) if data.app_password else None
        )
        encrypted_client_id = (
            encryption_service.encrypt(data.client_id) if data.client_id else None
        )
        encrypted_client_secret = (
            encryption_service.encrypt(data.client_secret) if data.client_secret else None
        )

        config = GmailConfiguration(
            application_id=data.application_id,
            name=data.name,
            email_address=data.email_address,
            auth_type=data.auth_type,
            smtp_host=data.smtp_host,
            smtp_port=data.smtp_port,
            encrypted_app_password=encrypted_app_password,
            encrypted_client_id=encrypted_client_id,
            encrypted_client_secret=encrypted_client_secret,
            is_active=data.is_active,
        )
        await self.repo.add(config)
        return config

    async def update_config(
        self, config_id: uuid.UUID, data: GmailConfigUpdate, app_id: uuid.UUID | None = None
    ) -> GmailConfiguration:
        """Updates configuration properties or rotates password/credentials."""
        if app_id:
            config = await self.repo.get_by_id_and_app(config_id, app_id)
        else:
            config = await self.repo.get_by_id(config_id)

        if not config:
            raise NotFoundException(f"Email configuration {config_id} not found")

        if data.name:
            config.name = data.name
        if data.email_address:
            config.email_address = data.email_address
        if data.auth_type:
            config.auth_type = data.auth_type
        if data.smtp_host:
            config.smtp_host = data.smtp_host
        if data.smtp_port:
            config.smtp_port = data.smtp_port
        if data.is_active is not None:
            config.is_active = data.is_active
        if data.app_password:
            config.encrypted_app_password = encryption_service.encrypt(data.app_password)
        if data.client_id:
            config.encrypted_client_id = encryption_service.encrypt(data.client_id)
        if data.client_secret:
            config.encrypted_client_secret = encryption_service.encrypt(data.client_secret)

        await self.session.flush()
        return config

    async def get_config(
        self, config_id: uuid.UUID, app_id: uuid.UUID | None = None
    ) -> GmailConfiguration:
        """Retrieves configuration by ID."""
        if app_id:
            config = await self.repo.get_by_id_and_app(config_id, app_id)
        else:
            config = await self.repo.get_by_id(config_id)

        if not config:
            raise NotFoundException(f"Email configuration {config_id} not found")
        return config

    async def list_configs(
        self, app_id: uuid.UUID, offset: int = 0, limit: int = 100
    ) -> Sequence[GmailConfiguration]:
        """Lists configurations belonging to an application."""
        return await self.repo.list_by_app(app_id, offset=offset, limit=limit)

    async def generate_oauth_url(self, config_id: uuid.UUID) -> tuple[str, str]:
        """Generates Google OAuth2 consent URL."""
        config = await self.get_config(config_id)
        if not config.encrypted_client_id:
            raise ValueError("Configuration lacks OAuth Client ID")

        client_id = encryption_service.decrypt(config.encrypted_client_id)
        state = str(config.id)

        params = {
            "client_id": client_id,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": config.scopes,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        auth_url = f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"
        return auth_url, state

    async def handle_oauth_callback(self, code: str, state: str) -> GmailConfiguration:
        """Exchanges authorization code for OAuth tokens and updates configuration."""
        try:
            config_id = uuid.UUID(state)
        except ValueError:
            raise NotFoundException("Invalid OAuth state parameter")

        config = await self.get_config(config_id)
        client_id = encryption_service.decrypt(config.encrypted_client_id)
        client_secret = encryption_service.decrypt(config.encrypted_client_secret)

        token_payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(self.GOOGLE_TOKEN_URL, data=token_payload)

        if res.status_code != 200:
            raise RuntimeError(f"Google token exchange failed: {res.text}")

        token_data = res.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        if access_token:
            config.encrypted_access_token = encryption_service.encrypt(access_token)
            config.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        if refresh_token:
            config.encrypted_refresh_token = encryption_service.encrypt(refresh_token)

        await self.session.flush()
        return config

    async def get_decrypted_credentials(
        self, config: GmailConfiguration
    ) -> dict[str, Any]:
        """Decrypts credentials for provider initialization."""
        app_password = (
            encryption_service.decrypt(config.encrypted_app_password)
            if config.encrypted_app_password
            else None
        )
        client_id = (
            encryption_service.decrypt(config.encrypted_client_id)
            if config.encrypted_client_id
            else None
        )
        client_secret = (
            encryption_service.decrypt(config.encrypted_client_secret)
            if config.encrypted_client_secret
            else None
        )
        refresh_token = (
            encryption_service.decrypt(config.encrypted_refresh_token)
            if config.encrypted_refresh_token
            else None
        )
        access_token = (
            encryption_service.decrypt(config.encrypted_access_token)
            if config.encrypted_access_token
            else None
        )

        return {
            "email_address": config.email_address,
            "auth_type": config.auth_type,
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "app_password": app_password,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "token_expiry": config.token_expiry,
        }

    async def update_refreshed_tokens(
        self, config: GmailConfiguration, new_tokens: dict
    ) -> None:
        """Persists newly refreshed OAuth tokens."""
        if "access_token" in new_tokens:
            config.encrypted_access_token = encryption_service.encrypt(new_tokens["access_token"])
        if "token_expiry" in new_tokens:
            config.token_expiry = new_tokens["token_expiry"]
        await self.session.flush()

    async def test_configuration(
        self, config_id: uuid.UUID, test_recipient: str
    ) -> dict[str, str | bool]:
        """Tests sending a sample email via App Password or OAuth."""
        config = await self.get_config(config_id)
        creds = await self.get_decrypted_credentials(config)

        provider = GmailProvider(
            email_address=str(creds["email_address"]),
            auth_type=creds["auth_type"],
            app_password=creds["app_password"],
            smtp_host=creds["smtp_host"],
            smtp_port=creds["smtp_port"],
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            refresh_token=creds["refresh_token"],
            access_token=creds["access_token"],
            token_expiry=creds["token_expiry"],
        )

        result = await provider.send({
            "to": [test_recipient],
            "subject": "Notification Gateway - Test Email",
            "text": "This is a test notification sent via Google App Password / SMTP.",
            "html": "<h3>Notification Gateway</h3><p>Test notification delivered successfully!</p>",
        })

        if result.new_tokens:
            await self.update_refreshed_tokens(config, result.new_tokens)

        return {
            "success": result.success,
            "message": result.error_message or f"Test email sent successfully (ID: {result.provider_message_id})",
        }

    async def delete_config(self, config_id: uuid.UUID) -> None:
        """Deletes a Gmail/SMTP configuration."""
        config = await self.get_config(config_id)
        await self.repo.delete(config)
        await self.session.flush()
