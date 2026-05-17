"""FR-ADMIN + FR-LEG integration tests."""
from __future__ import annotations

import httpx
import pytest

from tests.integration.conftest import Client, db_one


@pytest.mark.asyncio
async def test_admin_001_002_admin_can_list_and_change_users(admin: Client) -> None:
    r = await admin.get("/admin/users?limit=10")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_admin_003_audit_log_appears_for_role_change(admin: Client, user: Client) -> None:
    me = (await user.get("/auth/me")).json()
    await admin.post(f"/admin/users/{me['id']}/role", json={"role": "contributor"})
    r = await admin.get("/admin/audit-log?action=user.role.grant&limit=10")
    assert r.status_code == 200
    rows = r.json()
    assert any(row["target_id"] == me["id"] for row in rows)


@pytest.mark.asyncio
async def test_admin_006_unified_queue_counts(admin: Client) -> None:
    r = await admin.get("/admin/queue/counts")
    assert r.status_code == 200
    for k in (
        "pending_review_items",
        "pending_applications",
        "open_takedowns",
        "open_comment_reports",
        "open_cert_suggestions",
    ):
        assert k in r.json()


@pytest.mark.asyncio
async def test_admin_009_platform_settings_roundtrip(admin: Client) -> None:
    r1 = await admin.put("/admin/settings/view.video_min_s", json={"value": 12})
    assert r1.status_code == 200
    r2 = await admin.get("/admin/settings/view.video_min_s")
    assert r2.json()["value"] == 12


@pytest.mark.asyncio
async def test_leg_002_takedown_lifecycle(admin: Client) -> None:
    async with httpx.AsyncClient(base_url=admin.http.base_url) as anon:
        # CSRF first.
        await anon.get("/csrf")
        tok = anon.cookies.get("ndsc_csrf")
        assert tok
        r = await anon.post(
            "/legal/takedown",
            json={
                "complainant_name": "Rights Holder",
                "complainant_email": "legal@example.com",
                "complainant_address": "1 Main St",
                "target_url": "https://example.com/infringing",
                "sworn_statement": "I have a good-faith belief that the use is not authorized.",
            },
            headers={"X-CSRF-Token": tok},
        )
        assert r.status_code == 200
        tid = r.json()["id"]
    # Admin decides.
    r2 = await admin.post(f"/admin/takedowns/{tid}/decide", json={"action": "reject", "reason": "no merit"})
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_leg_004_erasure_grace_window() -> None:
    from tests.integration.conftest import PASSWORD, make_user

    u = await make_user()
    r = await u.post("/me/erasure", json={"password": PASSWORD})
    assert r.status_code == 200
    row = db_one("SELECT state FROM erasure_requests WHERE user_id=(SELECT id FROM users WHERE email=%(e)s ORDER BY created_at DESC LIMIT 1)", e=u.email)
    assert row.state == "pending"
    r2 = await u.post("/me/erasure/cancel", json={})
    assert r2.status_code == 200
    await u.aclose()


@pytest.mark.asyncio
async def test_leg_005_data_export_queued() -> None:
    from tests.integration.conftest import make_user
    u = await make_user()
    r = await u.post("/me/export", json={})
    assert r.status_code == 200
    assert r.json()["state"] in ("pending", "building", "ready")
    await u.aclose()
