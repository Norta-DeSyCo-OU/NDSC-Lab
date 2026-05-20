"""Content-gate tests (amended FR-VIDEO-006, 2026-05-20).

Consumable payload — hosted-video playback, file downloads, embed players —
requires an authenticated account (any role). Item / collection / author
pages and article body text stay public. These tests pin that boundary and
guard against the previously-open `/uploads/{id}/url` IDOR.
"""
from __future__ import annotations

import httpx
import pytest

from tests.integration.conftest import BASE, Client, db_exec, make_user

# Minimal byte payload — sufficient for HTTP transport assertions.
MP4_BYTES = bytes.fromhex(
    "0000001c66747970697336340000020069736f346d6d703431"
    "0000000866726565" + "00" * 128
)


@pytest.mark.asyncio
async def test_signed_url_denied_for_other_users_draft(contributor: Client) -> None:
    """`/uploads/{id}/url` must not leak another contributor's unpublished
    draft attachment to an unrelated authenticated user.

    Regression: the endpoint previously presigned ANY `clean` attachment,
    ignoring parent-item state — an IDOR on draft content.
    """
    r = await contributor.post(
        "/items",
        json={"type": "video", "video_kind": "hosted", "title": "Private draft video"},
    )
    iid = r.json()["id"]
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="video_primary",
        filename="draft.mp4",
        mime="video/mp4",
        body=MP4_BYTES,
    )
    aid = up.json()["attachment_id"]
    # Force clean WITHOUT publishing the parent item — it stays a draft.
    db_exec("UPDATE attachments SET state='clean' WHERE id=%(aid)s", aid=aid)

    other = await make_user(role="user")
    try:
        # Unrelated user: cannot presign and cannot stream the draft attachment.
        denied_url = await other.get(f"/uploads/{aid}/url")
        assert denied_url.status_code == 404, denied_url.text
        denied_stream = await other.get(f"/uploads/{aid}/stream")
        assert denied_stream.status_code == 404, denied_stream.text
    finally:
        await other.aclose()

    # The owner CAN presign their own draft attachment (preview).
    owner_url = await contributor.get(f"/uploads/{aid}/url")
    assert owner_url.status_code == 200, owner_url.text


@pytest.mark.asyncio
async def test_anonymous_signed_url_requires_login(contributor: Client) -> None:
    """`/uploads/{id}/url` has no anonymous access at all (`require_user`)."""
    r = await contributor.post(
        "/items", json={"type": "video", "video_kind": "hosted", "title": "Url gate"}
    )
    iid = r.json()["id"]
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="video_primary",
        filename="x.mp4",
        mime="video/mp4",
        body=MP4_BYTES,
    )
    aid = up.json()["attachment_id"]
    async with httpx.AsyncClient(base_url=BASE) as anon:
        denied = await anon.get(f"/uploads/{aid}/url")
        assert denied.status_code == 401, denied.text


@pytest.mark.asyncio
async def test_embed_external_url_hidden_from_anonymous(
    contributor: Client, admin: Client, user: Client,
) -> None:
    """Embed-video `external_url` is consumable payload: withheld from
    anonymous `GET /items/{id}`, revealed to authenticated members.

    `video_kind` is retained either way so the frontend still knows to
    render the login gate rather than a broken player.
    """
    r = await contributor.post(
        "/items",
        json={
            "type": "video",
            "video_kind": "embed",
            "title": "Gated embed talk",
            "external_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "license": "cc-by-4.0",
        },
    )
    iid = r.json()["id"]
    await contributor.post(f"/items/{iid}/submit", json={})
    await admin.post(f"/admin/items/{iid}/approve", json={})

    async with httpx.AsyncClient(base_url=BASE) as anon:
        a = await anon.get(f"/items/{iid}")
        assert a.status_code == 200, a.text
        assert a.json()["external_url"] is None
        assert a.json()["video_kind"] == "embed"

    m = await user.get(f"/items/{iid}")
    assert m.status_code == 200, m.text
    assert m.json()["external_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.asyncio
async def test_article_body_stays_public(contributor: Client, admin: Client) -> None:
    """Article body text is NOT gated — it stays readable without an account
    (only article *attachments* require login)."""
    r = await contributor.post(
        "/items",
        json={"type": "article", "title": "Open article", "body_md": "# Heading\n\nReadable."},
    )
    iid = r.json()["id"]
    await contributor.post(f"/items/{iid}/submit", json={})
    await admin.post(f"/admin/items/{iid}/approve", json={})

    async with httpx.AsyncClient(base_url=BASE) as anon:
        a = await anon.get(f"/items/{iid}")
        assert a.status_code == 200, a.text
        assert "Readable." in (a.json()["body_html"] or "")
