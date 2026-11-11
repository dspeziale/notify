"""Pydantic schemas for Audit Logs."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """View schema for an immutable audit log entry."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_type: str
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    status: str
    details: str | None
    ip_address: str | None
    created_at: datetime

