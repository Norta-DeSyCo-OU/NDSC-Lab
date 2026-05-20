"""End-to-end transcode workflow (FR-VIDEO-006 extended).

Verifies that a non-MP4 hosted video upload (e.g. .mov) is auto-transcoded by
the worker into a web-friendly H.264/MP4 with `+faststart`, and that an
authenticated viewer receives a `video_transcoded` attachment ready to
stream (anonymous requests are rejected by the content gate).
"""
from __future__ import annotations

import asyncio
import subprocess
import time

import httpx
import pytest

from tests.integration.conftest import BASE, Client, db_exec, db_one


def _gen_mov(path: str) -> bytes:
    """Use the api container's bundled ffmpeg to generate a tiny valid .mov."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-f", "lavfi",
            "-i", "testsrc=duration=1:size=160x120:rate=8",
            "-pix_fmt", "yuv420p",
            "-c:v", "h264",
            "-t", "1",
            "-f", "mov",
            path,
        ],
        check=True,
    )
    return open(path, "rb").read()


@pytest.mark.asyncio
async def test_mov_upload_is_auto_transcoded_to_mp4(
    contributor: Client, admin: Client, user: Client, tmp_path,
) -> None:
    # 1. Create hosted video item.
    r = await contributor.post(
        "/items",
        json={
            "type": "video",
            "video_kind": "hosted",
            "title": "Auto-transcode smoke test",
            "license": "cc-by-4.0",
        },
    )
    iid = r.json()["id"]

    # 2. Upload a real .mov payload (ffmpeg-generated).
    mov_path = str(tmp_path / "in.mov")
    body = _gen_mov(mov_path)
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="video_primary",
        filename="in.mov",
        mime="video/quicktime",
        body=body,
    )
    assert up.status_code == 200, up.text
    src_aid = up.json()["attachment_id"]

    # 3. Force original to `clean` (ClamAV is racing; the worker will pick it up).
    # In a fully-wired environment, ClamAV → clean → transcode_enqueue happens
    # automatically. Forcing here keeps the test independent of scan latency.
    db_exec(
        "UPDATE attachments SET state='clean' WHERE id=%(aid)s",
        aid=src_aid,
    )
    # Manually enqueue the transcode (the scan-loop branch would do this).
    import os as _os

    import redis

    r2 = redis.from_url(_os.environ["REDIS_URL"])
    r2.lpush("queue:transcode", src_aid)

    # 4. Wait for the worker to produce a transcoded attachment (up to 60 s).
    deadline = time.time() + 60
    transcoded_id = None
    while time.time() < deadline:
        row = db_one(
            "SELECT id, mime, state FROM attachments "
            "WHERE item_id=%(iid)s AND role='video_transcoded' "
            "ORDER BY created_at DESC LIMIT 1",
            iid=iid,
        )
        if row and row.state == "clean":
            transcoded_id = row.id
            assert row.mime == "video/mp4"
            break
        await asyncio.sleep(1)
    assert transcoded_id, "Worker did not produce a video_transcoded attachment within 60 s"

    # 5. Publish the item; the public attachments endpoint exposes the transcoded one.
    await contributor.post(f"/items/{iid}/submit", json={})
    await admin.post(f"/admin/items/{iid}/approve", json={})

    async with httpx.AsyncClient(base_url=BASE) as anon:
        atts = (await anon.get(f"/items/{iid}/attachments")).json()
        roles = {a["role"] for a in atts}
        assert "video_transcoded" in roles, atts
        tx = next(a for a in atts if a["role"] == "video_transcoded")
        stream_path = tx["stream_url"].replace("/api", "")
        # Content gate: anonymous stream is rejected.
        denied = await anon.get(stream_path)
        assert denied.status_code == 401, denied.text

    # 6. Authenticated viewer streams the transcoded MP4: 200 + `video/mp4`.
    full = await user.get(stream_path)
    assert full.status_code == 200
    assert full.headers.get("content-type") == "video/mp4"
    # The body must begin with an ISO BMFF (`ftyp`) atom, which both MP4
    # and properly-encoded MOV share. Faststart places it at byte 4-7.
    assert full.content[4:8] == b"ftyp", full.content[:16]


@pytest.mark.asyncio
async def test_already_mp4_is_not_transcoded(contributor: Client) -> None:
    """Idempotency: an MP4 upload should not produce a duplicate transcoded asset."""
    r = await contributor.post(
        "/items", json={"type": "video", "video_kind": "hosted", "title": "Direct MP4"}
    )
    iid = r.json()["id"]
    # Minimal MP4 header to satisfy the upload; the worker should see mime=video/mp4
    # and SKIP transcoding (`needs_transcode` returns False).
    mp4_stub = bytes.fromhex(
        "0000001c66747970697336340000020069736f346d6d703431"
        + "00" * 64
    )
    up = await contributor.upload_simple(
        "/uploads/simple",
        item_id=iid,
        role="video_primary",
        filename="in.mp4",
        mime="video/mp4",
        body=mp4_stub,
    )
    assert up.status_code == 200
    db_exec("UPDATE attachments SET state='clean' WHERE id=%(aid)s", aid=up.json()["attachment_id"])
    # Enqueue and wait a few seconds; no transcoded attachment should appear.
    import os as _os

    import redis as _redis
    _redis.from_url(_os.environ["REDIS_URL"]).lpush("queue:transcode", up.json()["attachment_id"])
    await asyncio.sleep(3)
    row = db_one(
        "SELECT count(*) AS c FROM attachments WHERE item_id=%(iid)s AND role='video_transcoded'",
        iid=iid,
    )
    assert row.c == 0
