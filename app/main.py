"""FastAPI main application entrypoint."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.endpoints.health import router as root_health_router
from app.api.v1.endpoints.metrics import router as root_metrics_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import GatewayException
from app.core.logging import setup_logging
from app.database.base import Base
from app.database.session import engine
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    setup_logging(debug=settings.DEBUG)
    # Ensure database schema is initialized (guarded against concurrent worker race conditions)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        # Schema already created or being created by another worker
        pass
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise Multi-Application Notification Gateway with Telegram & Gmail support",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)


# Exception Handlers
@app.exception_handler(GatewayException)
async def gateway_exception_handler(request: Request, exc: GatewayException):
    """Handles domain-specific Gateway exceptions."""
    headers = {}
    if hasattr(exc, "retry_after"):
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles Pydantic request validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": exc.errors(),
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unexpected internal errors."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred",
            },
        },
    )


# Root routes
app.include_router(root_health_router)
app.include_router(root_metrics_router)

# Versioned API routes
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

