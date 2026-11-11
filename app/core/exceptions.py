"""Custom exception hierarchy for the Notification Gateway."""

from typing import Any


class GatewayException(Exception):
    """Base class for all application exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Any = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details


class AuthenticationException(GatewayException):
    """Raised when authentication fails (missing, invalid, or expired API Key)."""

    def __init__(self, message: str = "Invalid or missing API key", details: Any = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_FAILED",
            details=details,
        )


class ForbiddenException(GatewayException):
    """Raised when the client lacks necessary permissions or is disabled."""

    def __init__(self, message: str = "Access forbidden for this resource", details: Any = None):
        super().__init__(
            message=message,
            status_code=403,
            error_code="PERMISSION_DENIED",
            details=details,
        )


class NotFoundException(GatewayException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "Resource not found", details: Any = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            details=details,
        )


class ConflictException(GatewayException):
    """Raised when a conflict occurs (e.g. duplicate idempotency key or existing entity)."""

    def __init__(self, message: str = "Resource conflict", details: Any = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details,
        )


class RateLimitExceededException(GatewayException):
    """Raised when application rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please retry later.",
        retry_after: int = 60,
    ):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after_seconds": retry_after},
        )
        self.retry_after = retry_after


class ProviderException(GatewayException):
    """Raised when a notification provider encounters an error."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int = 502,
        is_transient: bool = False,
        raw_error: str | None = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=f"PROVIDER_ERROR_{provider.upper()}",
            details={"provider": provider, "transient": is_transient, "raw_error": raw_error},
        )
        self.provider = provider
        self.is_transient = is_transient
        self.raw_error = raw_error


class CryptoException(GatewayException):
    """Raised when encryption or decryption operations fail."""

    def __init__(self, message: str = "Cryptographic operation failed"):
        super().__init__(
            message=message,
            status_code=500,
            error_code="CRYPTOGRAPHIC_ERROR",
        )
