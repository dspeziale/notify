"""Audit service for logging administrative operations and configuration mutations."""

import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import redact_sensitive_text
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repo import AuditLogRepository


class AuditService:
    """Records security and administrative audit entries."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AuditLogRepository(session)

    async def log_event(
        self,
        actor_type: str,
        action: str,
        resource_type: str,
        actor_id: str | None = None,
        resource_id: str | None = None,
        status: str = "success",
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Saves a sanitized audit event."""
        serialized_details = None
        if details:
            # Redact sensitive fields if any were passed
            clean_details = {}
            for k, v in details.items():
                if any(secret_term in str(k).lower() for secret_term in ["token", "secret", "password", "key"]):
                    clean_details[k] = "[REDACTED]"
                elif isinstance(v, str):
                    clean_details[k] = redact_sensitive_text(v)
                else:
                    clean_details[k] = v
            serialized_details = json.dumps(clean_details)

        audit = AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            details=serialized_details,
            ip_address=ip_address,
        )
        await self.repo.add(audit)
        return audit

