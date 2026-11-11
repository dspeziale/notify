"""Administrative endpoints for querying audit logs."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_admin_auth
from app.repositories.audit_log_repo import AuditLogRepository
from app.schemas.audit_log import AuditLogResponse
from app.schemas.common import APIResponse

router = APIRouter(
    prefix="/admin/audit-logs",
    tags=["Admin - Audit Logs"],
    dependencies=[Depends(require_admin_auth)],
)


@router.get("", response_model=APIResponse[list[AuditLogResponse]], summary="List audit logs")
async def list_audit_logs(
    offset: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves immutable audit trail of administrative and security events."""
    repo = AuditLogRepository(db)
    logs = await repo.list_recent(offset=offset, limit=limit)
    return APIResponse(data=[AuditLogResponse.model_validate(log) for log in logs])

