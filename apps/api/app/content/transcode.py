"""Auto-transcode uploaded videos to web-friendly H.264 MP4.

After ClamAV marks a `video_primary` attachment as `clean`, the worker enqueues
a transcode job. ffmpeg pipes the bytes from R2 → re-encodes to H.264/AAC with
`+faststart` → uploads back to R2 → inserts a new `Attachment(role='video_transcoded')`.

The frontend `<ItemPlayer>` and the public `/items/{id}/attachments` endpoint
prefer the transcoded asset when present.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from typing import Any

import aioboto3
from sqlalchemy import select

from app.content.models import Attachment, Item
from app.core.db import session_scope
from app.core.r2 import presign_get
from app.core.settings import get_settings
from app.core.telemetry import log

# Anything not already a clean H.264/MP4 should be re-encoded. We trigger on
# anything other than `video/mp4` to be safe; ffmpeg will be a no-op-equivalent
# fast remux for files that are already H.264+AAC in an MP4 container.
TRANSCODE_MIME_TRIGGERS = {
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
    "video/mpeg",
    "video/ogg",
    "video/3gpp",
    "application/octet-stream",
}


def needs_transcode(mime: str | None) -> bool:
    if not mime:
        return True
    return mime != "video/mp4"


async def transcode_one(attachment_id: str) -> None:
    """Transcode a single attachment in place. Idempotent: skips if a
    `video_transcoded` sibling already exists for the same item.
    """
    settings = get_settings()
    async with session_scope() as s:
        att = await s.scalar(select(Attachment).where(Attachment.id == attachment_id))
        if not att or att.role != "video_primary":
            return
        if att.state not in ("clean", "scanning"):
            return
        # Idempotency: skip if already transcoded for this item.
        existing = await s.scalar(
            select(Attachment).where(
                Attachment.item_id == att.item_id,
                Attachment.role == "video_transcoded",
                Attachment.state != "deleted",
            )
        )
        if existing:
            log.info("transcode_skip_existing", attachment_id=att.id, transcoded_id=existing.id)
            return
        if not needs_transcode(att.mime):
            log.info("transcode_skip_already_mp4", attachment_id=att.id, mime=att.mime)
            return
        item = await s.scalar(select(Item).where(Item.id == att.item_id))
        if not item:
            return

    # Fetch input → temp file → ffmpeg → temp output → upload.
    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "input.bin")
        out_path = os.path.join(tmp, "output.mp4")

        url = await presign_get(att.r2_key, expires=900)
        # Pull via aiohttp/httpx to avoid blocking the loop on a large download.
        import httpx

        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(in_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(1024 * 64):
                        f.write(chunk)

        log.info("transcode_start", attachment_id=att.id, in_bytes=os.path.getsize(in_path))
        # ffmpeg: H.264 (libx264) + AAC + faststart so the player can begin
        # playback before the whole file is downloaded.
        cmd = [
            "ffmpeg",
            "-y",
            "-i", in_path,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-f", "mp4",
            out_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.warning(
                "transcode_failed",
                attachment_id=att.id,
                returncode=proc.returncode,
                stderr=stderr.decode("utf-8", errors="replace")[-2000:],
            )
            return
        size_out = os.path.getsize(out_path)
        log.info("transcode_done", attachment_id=att.id, out_bytes=size_out)

        # Upload to R2.
        new_key = att.r2_key.rsplit("/", 2)[0] + "/video_transcoded/web.mp4"
        with open(out_path, "rb") as f:
            data = f.read()
        sess = aioboto3.Session()
        async with sess.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            region_name=settings.r2_region,
            aws_access_key_id=settings.r2_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        ) as c:
            await c.put_object(
                Bucket=settings.r2_hot_bucket,
                Key=new_key,
                Body=data,
                ContentType="video/mp4",
            )

        # Insert new attachment row, state=clean (it's our own output).
        async with session_scope() as s:
            new_att = Attachment(
                owner_user_id=att.owner_user_id,
                item_id=att.item_id,
                role="video_transcoded",
                r2_key=new_key,
                bytes=size_out,
                mime="video/mp4",
                state="clean",
            )
            s.add(new_att)
            await s.flush()
            log.info("transcode_attachment_added", source=att.id, new_id=new_att.id, key=new_key)
