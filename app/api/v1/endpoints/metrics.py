"""Prometheus metrics endpoint."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

router = APIRouter(tags=["Metrics"])

NOTIFICATIONS_TOTAL = Counter(
    "notifications_total",
    "Total dispatched notifications count",
    ["provider", "status"],
)

NOTIFICATIONS_LATENCY = Histogram(
    "notifications_delivery_latency_seconds",
    "Time taken to dispatch notification through provider",
    ["provider"],
)

RATE_LIMIT_EXCEEDED = Counter(
    "rate_limit_exceeded_total",
    "Total requests rejected due to rate limiting",
    ["application_id"],
)


@router.get("/metrics", summary="Prometheus operational metrics")
def metrics():
    """Returns Prometheus scrape targets."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

