"""Integration tests for application administration and API key lifecycle."""

import pytest


@pytest.mark.asyncio
async def test_admin_auth_required(client):
    # Unauthenticated request must be rejected with 401
    res = await client.get("/api/v1/admin/applications")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_FAILED"

    # Invalid key must be rejected
    res_bad = await client.get(
        "/api/v1/admin/applications", headers={"X-Admin-API-Key": "invalid-admin-key"}
    )
    assert res_bad.status_code == 401


@pytest.mark.asyncio
async def test_application_lifecycle(client, admin_headers):
    # 1. Create Application
    create_payload = {
        "name": "Finance App",
        "description": "Billing notifications",
        "rate_limit_per_minute": 50,
        "permissions": ["telegram:send"],
    }
    create_res = await client.post(
        "/api/v1/admin/applications", json=create_payload, headers=admin_headers
    )
    assert create_res.status_code == 200
    created_app = create_res.json()["data"]
    app_id = created_app["id"]
    initial_key = created_app["initial_api_key"]["raw_api_key"]
    assert initial_key.startswith("ng_live_")

    # 2. Duplicate name conflict (409)
    dup_res = await client.post(
        "/api/v1/admin/applications", json=create_payload, headers=admin_headers
    )
    assert dup_res.status_code == 409

    # 3. List applications
    list_res = await client.get("/api/v1/admin/applications", headers=admin_headers)
    assert list_res.status_code == 200
    assert any(a["id"] == app_id for a in list_res.json()["data"])

    # 4. Get application detail
    detail_res = await client.get(f"/api/v1/admin/applications/{app_id}", headers=admin_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["data"]["name"] == "Finance App"

    # 5. Update application (disable)
    update_res = await client.patch(
        f"/api/v1/admin/applications/{app_id}",
        json={"status": "disabled"},
        headers=admin_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["status"] == "disabled"

    # Attempting to use disabled application's API Key should return 403
    app_client_res = await client.get(
        "/api/v1/notifications", headers={"X-API-Key": initial_key}
    )
    assert app_client_res.status_code == 403
    assert app_client_res.json()["error"]["code"] == "PERMISSION_DENIED"

    # Re-enable application
    await client.patch(
        f"/api/v1/admin/applications/{app_id}",
        json={"status": "active"},
        headers=admin_headers,
    )

    # 6. Regenerate API Key
    regen_res = await client.post(
        f"/api/v1/admin/applications/{app_id}/regenerate-key", headers=admin_headers
    )
    assert regen_res.status_code == 200
    new_raw_key = regen_res.json()["data"]["raw_api_key"]
    assert new_raw_key != initial_key

    # Old key is revoked (401)
    old_key_res = await client.get(
        "/api/v1/notifications", headers={"X-API-Key": initial_key}
    )
    assert old_key_res.status_code == 401

    # New key works (200)
    new_key_res = await client.get(
        "/api/v1/notifications", headers={"X-API-Key": new_raw_key}
    )
    assert new_key_res.status_code == 200

    # 7. Delete application
    del_res = await client.delete(
        f"/api/v1/admin/applications/{app_id}", headers=admin_headers
    )
    assert del_res.status_code == 200
    assert del_res.json()["data"] is True

    # Application no longer exists (404)
    get_del_res = await client.get(
        f"/api/v1/admin/applications/{app_id}", headers=admin_headers
    )
    assert get_del_res.status_code == 404

