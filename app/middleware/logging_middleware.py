"""Request auditing and performance logging middleware."""

import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming HTTP requests and response latencies without sensitive headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id

        # Skip logging health and metrics spam
        if request.url.path not in ("/health", "/api/v1/health", "/metrics"):
            logger.info(
                "%s %s - status=%d - duration=%.2fms - ip=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                client_ip,
                extra={"request_id": request_id},
            )

        return response

