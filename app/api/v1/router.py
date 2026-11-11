"""Main API v1 router consolidating all sub-routers."""

from fastapi import APIRouter
from app.api.v1.endpoints.admin.applications import router as applications_router
from app.api.v1.endpoints.admin.audit import router as audit_router
from app.api.v1.endpoints.admin.gmail_configs import router as gmail_configs_router
from app.api.v1.endpoints.admin.telegram_configs import router as telegram_configs_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.metrics import router as metrics_router
from app.api.v1.endpoints.notifications import router as notifications_router

api_v1_router = APIRouter()

# Client Endpoints
api_v1_router.include_router(notifications_router)

# Admin Endpoints
api_v1_router.include_router(applications_router)
api_v1_router.include_router(telegram_configs_router)
api_v1_router.include_router(gmail_configs_router)
api_v1_router.include_router(audit_router)

# Health & Metrics
api_v1_router.include_router(health_router)
api_v1_router.include_router(metrics_router)

