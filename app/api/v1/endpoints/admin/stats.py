"""Admin statistics and dashboard summary endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_admin_auth
from app.models.application import Application
from app.models.gmail_config import GmailConfiguration
from app.models.notification import Notification
from app.models.telegram_config import TelegramConfiguration
from app.schemas.common import APIResponse

router = APIRouter(prefix="/admin/stats", tags=["Admin - Stats"])


@router.get(
    "",
    summary="Get overall system statistics (Admin only)",
)
async def get_system_stats(
    admin_auth: bool = Depends(require_admin_auth),
    db: AsyncSession = Depends(get_db),
):
    """Calculates live metrics for the administrative dashboard."""
    # Applications
    total_apps_q = await db.execute(select(func.count(Application.id)))
    total_apps = total_apps_q.scalar() or 0

    active_apps_q = await db.execute(
        select(func.count(Application.id)).where(Application.status == "active")
    )
    active_apps = active_apps_q.scalar() or 0

    # Telegram Configs
    total_tg_q = await db.execute(select(func.count(TelegramConfiguration.id)))
    total_tg = total_tg_q.scalar() or 0

    active_tg_q = await db.execute(
        select(func.count(TelegramConfiguration.id)).where(TelegramConfiguration.is_active == True)  # noqa: E712
    )
    active_tg = active_tg_q.scalar() or 0

    # Gmail Configs
    total_gmail_q = await db.execute(select(func.count(GmailConfiguration.id)))
    total_gmail = total_gmail_q.scalar() or 0

    active_gmail_q = await db.execute(
        select(func.count(GmailConfiguration.id)).where(GmailConfiguration.is_active == True)  # noqa: E712
    )
    active_gmail = active_gmail_q.scalar() or 0

    # Notifications
    total_notifs_q = await db.execute(select(func.count(Notification.id)))
    total_notifs = total_notifs_q.scalar() or 0

    sent_notifs_q = await db.execute(
        select(func.count(Notification.id)).where(Notification.status == "sent")
    )
    sent_notifs = sent_notifs_q.scalar() or 0

    failed_notifs_q = await db.execute(
        select(func.count(Notification.id)).where(Notification.status == "failed")
    )
    failed_notifs = failed_notifs_q.scalar() or 0

    pending_notifs_q = await db.execute(
        select(func.count(Notification.id)).where(Notification.status.in_(["pending", "processing"]))
    )
    pending_notifs = pending_notifs_q.scalar() or 0

    # Group by provider
    tg_notifs_q = await db.execute(
        select(func.count(Notification.id)).where(Notification.provider == "telegram")
    )
    tg_notifs = tg_notifs_q.scalar() or 0

    email_notifs_q = await db.execute(
        select(func.count(Notification.id)).where(Notification.provider == "email")
    )
    email_notifs = email_notifs_q.scalar() or 0

    return APIResponse(
        data={
            "applications": {
                "total": total_apps,
                "active": active_apps,
                "disabled": total_apps - active_apps,
            },
            "telegram": {
                "total_configs": total_tg,
                "active_configs": active_tg,
                "notifications_sent": tg_notifs,
            },
            "gmail": {
                "total_configs": total_gmail,
                "active_configs": active_gmail,
                "notifications_sent": email_notifs,
            },
            "notifications": {
                "total": total_notifs,
                "sent": sent_notifs,
                "failed": failed_notifs,
                "pending": pending_notifs,
                "success_rate": round((sent_notifs / total_notifs * 100), 1) if total_notifs > 0 else 100.0,
            },
        }
    )
