"""FastAPI main application entrypoint."""

import asyncio
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
from app.services.telegram_polling_service import run_telegram_inbound_poller


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

    # Start background polling for Telegram inbound messages
    polling_task = asyncio.create_task(run_telegram_inbound_poller())

    yield
    # Shutdown
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="VORTEX: Versatile Omnichannel Routing & Telegram-Email eXchange. Enterprise Notification Center.",
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

# Static Files & Dashboard Web UI
from pathlib import Path
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serves the application favicon."""
    fav_svg = static_dir / "favicon.svg"
    if fav_svg.exists():
        return FileResponse(fav_svg, media_type="image/svg+xml")
    return JSONResponse(status_code=204, content=None)


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page():
    """Serves the administrative Web Dashboard."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(status_code=404, content={"message": "Dashboard UI not found"})


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirects root URL directly to the dashboard."""
    return RedirectResponse(url="/dashboard")

