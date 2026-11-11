"""Common Pydantic schemas for API requests and responses."""

from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard API envelope response."""
    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorDetail(BaseModel):
    """Structured error payload."""
    code: str
    message: str
    details: dict | list | str | None = None


class ErrorResponse(BaseModel):
    """Standard error envelope response."""
    success: bool = False
    error: ErrorDetail
