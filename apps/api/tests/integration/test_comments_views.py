"""FR-COM + FR-VIEW integration tests."""
from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import Client, db_exec, make_user


async def _published_item(contributor: Client, admin: Client) -> str:
    r = await contributor.post(
        "/items", json={"type": "article", "title": "Discuss me here", "body_md": "x"}
    )
    iid = r.json()["id"]
    await contributor.post(f"/items/{iid}/submit", json={})
    await admin.post(f"/admin/items/{iid}/approve", json={})
    return iid


@pytest.mark.asyncio
async def test_com_001_user_can_post_comment(admin: Client, contributor: Client) -> None:
    iid = await _published_item(contributor, admin)
    u = await make_user()
    r = await u.post(f"/items/{iid}/comments", json={"body_md": "Looks good."})
    assert r.status_code == 200
    cid = r.json()["id"]
    listed = (await u.get(f"/items/{iid}/comments")).json()
    assert any(c["id"] == cid for c in listed)
    await u.aclose()


@pytest.mark.asyncio
async def test_com_002_author_edit_window_blocked_after_15min(admin: Client, contributor: Client) -> None:
    iid = await _published_item(contributor, admin)
    u = await make_user()
    r = await u.post(f"/items/{iid}/comments", json={"body_md": "First."})
    cid = r.json()["id"]
    # Push the row's created_at far back to simulate expiry.
    db_exec("UPDATE comments SET created_at = created_at - interval '1 hour' WHERE id=%(i)s", i=cid)
    r2 = await u.patch(f"/comments/{cid}", json={"body_md": "Edited."})
    assert r2.status_code == 400
    await u.aclose()


@pytest.mark.asyncio
async def test_com_003_admin_can_delete_comment(admin: Client, contributor: Client) -> None:
    iid = await _published_item(contributor, admin)
    u = await make_user()
    r = await u.post(f"/items/{iid}/comments", json={"body_md": "Hi"})
    cid = r.json()["id"]
    r2 = await admin.delete(f"/comments/{cid}")
    assert r2.status_code == 200
    listed = (await u.get(f"/items/{iid}/comments")).json()
    assert not any(c["id"] == cid for c in listed)
    await u.aclose()


@pytest.mark.asyncio
async def test_view_001_event_requires_analytics_consent(admin: Client, contributor: Client) -> None:
    iid = await _published_item(contributor, admin)
    u = await make_user()
    # User opted in to analytics by default in fixture.
    r = await u.post(
        "/events/view",
        json={
            "item_id": iid, "item_type": "article",
            "view_session_uuid": str(uuid.uuid4()),
            "watched_s": 10.0, "scroll_pct": 0.6,
        },
        headers={"Origin": "http://localhost"},
    )
    assert r.status_code == 204
    await u.aclose()


@pytest.mark.asyncio
async def test_view_005_admin_dashboard_returns_aggregates(admin: Client) -> None:
    r = await admin.get("/admin/analytics/items")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_view_007_non_admin_cannot_read_analytics(contributor: Client) -> None:
    r = await contributor.get("/admin/analytics/items")
    assert r.status_code == 403
