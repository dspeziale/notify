"""Abstract base class for notification providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderResult:
    """Standard execution result returned by a notification provider."""
    success: bool
    provider_message_id: str | None = None
    status_code: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    is_transient: bool = False
    new_tokens: dict[str, Any] | None = None  # Used when OAuth tokens are refreshed


class BaseNotificationProvider(ABC):
    """Abstract interface that all notification providers must implement."""

    @abstractmethod
    async def send(self, payload: dict[str, Any]) -> ProviderResult:
        """Dispatches notification payload to external provider."""
        pass

