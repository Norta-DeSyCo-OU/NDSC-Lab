"""FR-CONTENT + FR-ART + FR-VIDEO + FR-TM end-to-end."""
from __future__ import annotations

import pytest

from tests.integration.conftest import Client, db_one


@pytest.mark.asyncio
async def test_content_001_005_draft_submit_approve_flow(contributor: Client, admin: Client) -> None:
    # Draft.
    r = await contributor.post(
        "/items",
        json={
            "type": "article",
            "title": "ZKP for engineers",
            "body_md": "# ZKP\n\nA short intro with **bold** and `code`.",
            "license": "cc-by-4.0",
        },
    )
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["state"] == "draft"
    iid = item["id"]

    # Update.
    r2 = await contributor.patch(f"/items/{iid}", json={"summary": "Intro."})
    assert r2.status_code == 200

    # Submit for review.
    r3 = await contributor.post(f"/items/{iid}/submit", json={})
    assert r3.status_code == 200
    assert r3.json()["state"] == "pending_review"

    # Anonymous cannot fetch draft.
    import httpx
    async with httpx.AsyncClient(base_url=contributor.http.base_url) as anon:
        a = await anon.get(f"/items/{iid}")
        assert a.status_code == 404

    # Admin approves.
    r4 = await admin.post(f"/admin/items/{iid}/approve", json={})
    assert r4.status_code == 200
    assert r4.json()["state"] == "published"

    # Public can now read.
    async with httpx.AsyncClient(base_url=contributor.http.base_url) as anon:
        a = await anon.get(f"/items/{iid}")
        assert a.status_code == 200
        assert "<h1>ZKP</h1>" in a.json()["body_html"]


@pytest.mark.asyncio
async def test_content_010_license_persisted_and_changeable(contributor: Client) -> None:
    r = await contributor.post(
        "/items",
        json={"type": "article", "title": "License test item", "body_md": "x", "license": "cc-by-sa-4.0"},
    )
    assert r.status_code == 200
    assert r.json()["license"] == "cc-by-sa-4.0"
    row = db_one("SELECT license FROM items WHERE id=%(id)s", id=r.json()["id"])
    assert row.license == "cc-by-sa-4.0"


@pytest.mark.asyncio
async def test_video_003_embed_video_with_external_url(contributor: Client) -> None:
    r = await contributor.post(
        "/items",
        json={
            "type": "video",
            "video_kind": "embed",
            "title": "An embedded talk",
            "external_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "license": "cc-by-4.0",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["type"] == "video"


@pytest.mark.asyncio
async def test_art_001_002_003_markdown_pipeline_strips_xss(contributor: Client) -> None:
    r = await contributor.post(
        "/items",
        json={
            "type": "article",
            "title": "Markdown safety",
            "body_md": "Hello <script>alert(1)</script> [evil](javascript:alert(1)) <img src=x onerror=alert(1)>",
        },
    )
    assert r.status_code == 200
    html = r.json()["body_html"]
    assert "<script" not in html
    assert "onerror" not in html
    assert 'href="javascript:' not in html


@pytest.mark.asyncio
async def test_tm_001_can_create_teaching_material_with_external_url(contributor: Client) -> None:
    r = await contributor.post(
        "/items",
        json={
            "type": "teaching_material",
            "title": "Zenodo dataset",
            "external_url": "https://zenodo.org/record/123456",
        },
    )
    assert r.status_code == 200
    assert r.json()["type"] == "teaching_material"


@pytest.mark.asyncio
async def test_upload_simple_attaches_file_to_item(contributor: Client) -> None:
    r = await contributor.post(
        "/items", json={"type": "article", "title": "With attachment", "body_md": "x"}
    )
    iid = r.json()["id"]
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="article_attachment",
        filename="hello.txt",
        mime="text/plain",
        body=b"hello world",
    )
    assert up.status_code == 200, up.text
    j = up.json()
    assert j["state"] in ("scanning", "clean")
    listed = (await contributor.get(f"/uploads/by-item/{iid}")).json()
    assert any(a["id"] == j["attachment_id"] for a in listed)


@pytest.mark.asyncio
async def test_upload_rejects_disallowed_mime(contributor: Client) -> None:
    r = await contributor.post(
        "/items", json={"type": "article", "title": "Mime check", "body_md": "x"}
    )
    iid = r.json()["id"]
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="article_attachment",
        filename="evil.exe",
        mime="application/x-msdos-program",
        body=b"MZ\x00",
    )
    assert up.status_code == 400
    assert "mime_not_allowed" in up.text


@pytest.mark.asyncio
async def test_upload_path_traversal_sanitized(contributor: Client) -> None:
    r = await contributor.post(
        "/items", json={"type": "article", "title": "Traversal", "body_md": "x"}
    )
    iid = r.json()["id"]
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="article_attachment",
        filename="../../etc/passwd",
        mime="text/plain",
        body=b"hi",
    )
    assert up.status_code == 200
    assert "../" not in up.json()["r2_key"]
