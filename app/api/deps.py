"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from fastapi import Depends, Header, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AuthenticationException
from app.database.session import get_db_session
from app.models.application import Application
from app.services.auth_service import AuthService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides transactional SQLAlchemy async session."""
    async for session in get_db_session():
        yield session


async def get_current_application(
    api_key: str | None = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Application:
    """Authenticates the client application via X-API-Key header."""
    if not api_key:
        raise AuthenticationException("Header 'X-API-Key' is required")

    auth_service = AuthService(db)
    return await auth_service.authenticate_application(api_key)


async def require_admin_auth(
    admin_key: str | None = Depends(admin_key_header),
    api_key: str | None = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> bool:
    """Enforces administrative authentication via X-Admin-API-Key or admin X-API-Key."""
    key_to_check = admin_key or api_key
    if not key_to_check:
        raise AuthenticationException("Administrative authentication required ('X-Admin-API-Key')")

    auth_service = AuthService(db)
    return await auth_service.authenticate_admin(key_to_check)


def get_client_ip(request: Request) -> str:
    """Extracts client IP address safely from request headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

