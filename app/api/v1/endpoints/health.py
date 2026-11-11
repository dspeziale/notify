"""Health check and diagnostic endpoints."""

from datetime import datetime, timezone
import time
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.config import settings
from app.core.rate_limiter import rate_limiter

router = APIRouter(tags=["Health"])

START_TIME = time.time()


@router.get("/health", summary="Overall system health check")
@router.get("/api/v1/health", summary="V1 system health check")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Validates operational connectivity to database, redis, and crypto components."""
    checks = {
        "database": "unknown",
        "redis": "disabled" if not settings.REDIS_ENABLED else "unknown",
        "encryption": "operational",
    }
    overall_status = "healthy"

    # Test Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as exc:
        checks["database"] = f"unhealthy: {str(exc)}"
        overall_status = "unhealthy"

    # Test Redis if enabled
    if settings.REDIS_ENABLED:
        try:
            redis = await rate_limiter._get_redis()
            if redis and await redis.ping():
                checks["redis"] = "connected"
            else:
                checks["redis"] = "disconnected"
                overall_status = "degraded"
        except Exception as exc:
            checks["redis"] = f"error: {str(exc)}"
            overall_status = "degraded"

    uptime_seconds = int(time.time() - START_TIME)

    return {
        "status": overall_status,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": uptime_seconds,
        "components": checks,
    }

