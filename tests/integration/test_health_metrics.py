"""Integration tests for health checks and Prometheus metrics."""

import pytest


@pytest.mark.asyncio
async def test_health_endpoints(client):
    res1 = await client.get("/health")
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["status"] == "healthy"
    assert body1["components"]["database"] == "connected"

    res2 = await client.get("/api/v1/health")
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["status"] == "healthy"


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    res = await client.get("/metrics")
    assert res.status_code == 200
    content = res.text
    assert "notifications_total" in content
    assert "notifications_delivery_latency_seconds" in content

