"""Integration tests for Web Dashboard and administrative dashboard endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_dashboard_static_and_html_endpoints(client: AsyncClient):
    """Verifies that the dashboard HTML and static assets are correctly served."""
    # Root redirect
    root_res = await client.get("/", follow_redirects=False)
    assert root_res.status_code in [302, 307]
    assert root_res.headers.get("location") == "/dashboard"

    # Dashboard HTML
    dash_res = await client.get("/dashboard")
    assert dash_res.status_code == 200
    assert "text/html" in dash_res.headers.get("content-type", "")
    assert "VORTEX" in dash_res.text
    assert "table-wrapper" in dash_res.text

    # Static CSS
    css_res = await client.get("/static/css/dashboard.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers.get("content-type", "")

    # Static JS
    js_res = await client.get("/static/js/dashboard.js")
    assert js_res.status_code == 200


@pytest.mark.asyncio
async def test_admin_stats_and_notifications_endpoints(client: AsyncClient):
    """Verifies that admin stats and admin notification tracking endpoints function properly."""
    admin_headers = {"X-Admin-API-Key": settings.ADMIN_API_KEY}

    # Test stats endpoint
    stats_res = await client.get("/api/v1/admin/stats", headers=admin_headers)
    assert stats_res.status_code == 200
    stats_data = stats_res.json()["data"]
    assert "applications" in stats_data
    assert "telegram" in stats_data
    assert "gmail" in stats_data
    assert "notifications" in stats_data

    # Test admin notifications list endpoint
    notif_res = await client.get("/api/v1/admin/notifications", headers=admin_headers)
    assert notif_res.status_code == 200
    notifs_data = notif_res.json()["data"]
    assert isinstance(notifs_data, list)
