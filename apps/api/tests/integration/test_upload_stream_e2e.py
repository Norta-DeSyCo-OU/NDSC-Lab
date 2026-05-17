"""End-to-end upload → scan → publish → stream workflow.

Exercises FR-VIDEO-001..002 + FR-TM-001..002 + FR-CONTENT-005:
1. Contributor creates a hosted-video item.
2. Uploads a small `.mp4` payload via /uploads/simple.
3. Worker scans (clean / mocked stub if clamav unreachable).
4. Contributor submits for review.
5. Admin approves → published.
6. Public stream URL serves the bytes (HTTP 200 / partial 206 with Range).
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from tests.integration.conftest import BASE, Client, db_exec

# A tiny valid-ish MP4 header (won't actually play; sufficient for HTTP byte transport).
MP4_BYTES = bytes.fromhex(
    "0000001c66747970697336340000020069736f346d6d703431"
    "0000000866726565"
    + "00" * 256
)


async def _wait_clean(att_id: str, timeout: float = 30.0) -> None:
    """Poll DB until attachment state moves out of `scanning`."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        import os

        import psycopg2

        with psycopg2.connect(os.environ["DATABASE_URL"].replace("+asyncpg", "")) as c, c.cursor() as cur:
            cur.execute("SELECT state FROM attachments WHERE id=%s", (att_id,))
            row = cur.fetchone()
            if row and row[0] in ("clean", "quarantined", "deleted"):
                return
        await asyncio.sleep(0.5)


@pytest.mark.asyncio
async def test_video_upload_to_streaming_end_to_end(contributor: Client, admin: Client) -> None:
    # 1. Create hosted-video item.
    r = await contributor.post(
        "/items",
        json={
            "type": "video",
            "video_kind": "hosted",
            "title": "Test lecture video",
            "summary": "Smoke test for streaming",
            "license": "cc-by-4.0",
        },
    )
    assert r.status_code == 200, r.text
    iid = r.json()["id"]

    # 2. Upload bytes (simulate small MP4 payload).
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="video_primary",
        filename="lecture.mp4",
        mime="video/mp4",
        body=MP4_BYTES,
    )
    assert up.status_code == 200, up.text
    aid = up.json()["attachment_id"]

    # 3. Wait for ClamAV scan to terminate (worker drains queue:scan).
    # If clamav is unreachable in the test env the scan never completes; force clean for the test.
    await _wait_clean(aid, timeout=15.0)
    db_exec(
        "UPDATE attachments SET state='clean' WHERE id=%(aid)s AND state IN ('scanning','quarantined')",
        aid=aid,
    )

    # 4. Submit + admin approve.
    r2 = await contributor.post(f"/items/{iid}/submit", json={})
    assert r2.status_code == 200, r2.text
    r3 = await admin.post(f"/admin/items/{iid}/approve", json={})
    assert r3.status_code == 200, r3.text

    # 5. Public listing of attachments shows the clean video with a stream URL.
    async with httpx.AsyncClient(base_url=BASE) as anon:
        list_r = await anon.get(f"/items/{iid}/attachments")
        assert list_r.status_code == 200, list_r.text
        atts = list_r.json()
        primary = [a for a in atts if a["role"] == "video_primary" and a["state"] == "clean"]
        assert len(primary) == 1
        stream_path = primary[0]["stream_url"].replace("/api", "")  # strip Caddy prefix → api path

        # 6. Full GET returns 200 + bytes match.
        full = await anon.get(stream_path)
        assert full.status_code == 200, full.text
        assert full.content == MP4_BYTES
        assert full.headers.get("accept-ranges") == "bytes"

        # 7. Range request returns 206 + partial bytes.
        rng = await anon.get(stream_path, headers={"Range": "bytes=0-15"})
        assert rng.status_code == 206
        assert rng.content == MP4_BYTES[:16]


@pytest.mark.asyncio
async def test_teaching_material_upload_and_public_download(
    contributor: Client, admin: Client,
) -> None:
    r = await contributor.post(
        "/items",
        json={
            "type": "teaching_material",
            "title": "Sample dataset bundle",
            "summary": "tiny",
        },
    )
    iid = r.json()["id"]
    payload = b"col1,col2\n1,2\n3,4\n"
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="teaching_material_file",
        filename="data.csv",
        mime="text/csv",
        body=payload,
    )
    assert up.status_code == 200
    aid = up.json()["attachment_id"]
    await _wait_clean(aid, timeout=15.0)
    db_exec(
        "UPDATE attachments SET state='clean' WHERE id=%(aid)s AND state IN ('scanning','quarantined')",
        aid=aid,
    )

    await contributor.post(f"/items/{iid}/submit", json={})
    await admin.post(f"/admin/items/{iid}/approve", json={})

    async with httpx.AsyncClient(base_url=BASE) as anon:
        atts = (await anon.get(f"/items/{iid}/attachments")).json()
        primary = [a for a in atts if a["role"] == "teaching_material_file"][0]
        full = await anon.get(primary["stream_url"].replace("/api", ""))
        assert full.status_code == 200
        assert full.content == payload


@pytest.mark.asyncio
async def test_quarantined_attachment_is_hidden_from_public(
    contributor: Client, admin: Client,
) -> None:
    r = await contributor.post(
        "/items", json={"type": "video", "video_kind": "hosted", "title": "Risk content"}
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
    db_exec(
        "UPDATE attachments SET state='quarantined' WHERE id=%(aid)s",
        aid=aid,
    )
    # Publish.
    await contributor.post(f"/items/{iid}/submit", json={})
    await admin.post(f"/admin/items/{iid}/approve", json={})

    async with httpx.AsyncClient(base_url=BASE) as anon:
        atts = (await anon.get(f"/items/{iid}/attachments")).json()
        assert not any(a["role"] == "video_primary" for a in atts), (
            "Quarantined attachment must NOT be listed publicly"
        )
        # Direct stream URL also denied (404 for anon).
        stream = await anon.get(f"/uploads/{aid}/stream")
        assert stream.status_code == 404
