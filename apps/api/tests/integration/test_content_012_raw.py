"""FR-CONTENT-012 — author can read raw source, edit published item."""
from __future__ import annotations

import pytest

from tests.integration.conftest import Client, make_user


@pytest.mark.asyncio
async def test_content_012a_author_can_read_own_raw(contributor: Client) -> None:
    r = await contributor.post(
        "/items", json={"type": "article", "title": "Hello raw", "body_md": "# Hello\nworld"}
    )
    iid = r.json()["id"]
    raw = await contributor.get(f"/items/{iid}/raw")
    assert raw.status_code == 200, raw.text
    body = raw.json()
    assert body["body_md"] == "# Hello\nworld"
    assert body["type"] == "article"


@pytest.mark.asyncio
async def test_content_012a_non_owner_gets_404(contributor: Client) -> None:
    r = await contributor.post(
        "/items", json={"type": "article", "title": "Private body", "body_md": "secret"}
    )
    iid = r.json()["id"]
    other = await make_user(role="contributor")
    try:
        r2 = await other.get(f"/items/{iid}/raw")
        # 404 (no leak of existence) for non-owner non-admin.
        assert r2.status_code == 404
    finally:
        await other.aclose()


@pytest.mark.asyncio
async def test_content_012a_admin_can_read_any_raw(contributor: Client, admin: Client) -> None:
    r = await contributor.post(
        "/items", json={"type": "article", "title": "Visible to admin", "body_md": "raw text"}
    )
    iid = r.json()["id"]
    raw = await admin.get(f"/items/{iid}/raw")
    assert raw.status_code == 200
    assert raw.json()["body_md"] == "raw text"


@pytest.mark.asyncio
async def test_content_012c_author_can_patch_published_item(
    contributor: Client, admin: Client,
) -> None:
    # Create + publish.
    r = await contributor.post(
        "/items", json={"type": "article", "title": "Living article", "body_md": "v1"}
    )
    iid = r.json()["id"]
    await contributor.post(f"/items/{iid}/submit", json={})
    await admin.post(f"/admin/items/{iid}/approve", json={})

    # Author edits the published item.
    r2 = await contributor.patch(f"/items/{iid}", json={"body_md": "v2 — improved"})
    assert r2.status_code == 200, r2.text
    j = r2.json()
    # Still published, unchanged URL.
    assert j["state"] == "published"
    # Raw body updated.
    raw = await contributor.get(f"/items/{iid}/raw")
    assert raw.json()["body_md"] == "v2 — improved"
    # HTML re-rendered.
    pub = await contributor.get(f"/items/{iid}")
    assert "v2" in (pub.json().get("body_html") or "")


@pytest.mark.asyncio
async def test_content_012c_non_author_cannot_patch_published(
    contributor: Client, admin: Client,
) -> None:
    r = await contributor.post(
        "/items", json={"type": "article", "title": "Locked to author", "body_md": "v1"}
    )
    iid = r.json()["id"]
    await contributor.post(f"/items/{iid}/submit", json={})
    await admin.post(f"/admin/items/{iid}/approve", json={})

    other = await make_user(role="contributor")
    try:
        r2 = await other.patch(f"/items/{iid}", json={"body_md": "evil"})
        # Either 403 (auth'd but not owner) or 404 (existence-hiding). Both acceptable.
        assert r2.status_code in (403, 404)
    finally:
        await other.aclose()
