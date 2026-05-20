"""Direct-to-R2 multipart upload orchestration + simple-stream upload + ClamAV scan."""
from __future__ import annotations

from typing import Annotated, Any

import aioboto3
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.models import Attachment, Item
from app.core.db import get_session
from app.core.policy import Actor, PolicyError, authorize
from app.core.r2 import (
    complete_multipart_upload as _complete,
)
from app.core.r2 import (
    create_multipart_upload as _create_mpu,
)
from app.core.r2 import (
    delete_object,
    presign_get,
)
from app.core.security.csrf import require_csrf
from app.core.settings import get_settings
from app.identity.deps import current_actor, require_user
from app.legal.models import ContributorTunable

router = APIRouter(prefix="/uploads", tags=["content"])

ALLOWED_VIDEO_MIME = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-matroska",
    "video/x-m4v",
}
# Map common video extensions to a canonical allowed MIME when the OS reports
# `application/octet-stream` or a generic type. Lets us accept e.g. `.mov`
# files that Windows tags only by extension.
VIDEO_EXTENSION_MIME = {
    ".mp4": "video/mp4",
    ".m4v": "video/x-m4v",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".qt": "video/quicktime",
    ".mkv": "video/x-matroska",
}
ALLOWED_DOC_MIME = {
    "application/pdf",
    "application/zip",
    "application/x-7z-compressed",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/webp",
}



class CreateUploadIn(BaseModel):
    item_id: str
    role: str = Field(pattern="^(video_primary|article_attachment|teaching_material_file|profile_photo)$")
    mime: str
    bytes_size: int = Field(ge=1)
    filename: str = Field(min_length=1, max_length=255)


class CreateUploadOut(BaseModel):
    attachment_id: str
    upload_id: str
    r2_key: str
    bucket: str


@router.post("", response_model=CreateUploadOut)
async def begin_upload(
    body: CreateUploadIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> CreateUploadOut:
    require_csrf(request)
    item = await s.scalar(select(Item).where(Item.id == body.item_id))
    if not item or item.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="item_not_found")
    try:
        authorize(actor, "item.update", item)
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from e

    # MIME allowlist by role
    if body.role == "video_primary" and body.mime not in ALLOWED_VIDEO_MIME:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="mime_not_allowed")
    if body.role in {"article_attachment", "teaching_material_file", "profile_photo"} and body.mime not in ALLOWED_DOC_MIME:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="mime_not_allowed")

    settings = get_settings()

    # Quota + per-contributor tunable enforcement (FR-TM-003, FR-VIDEO-004, FR-ADMIN-008).
    tunable = await s.scalar(
        select(ContributorTunable).where(ContributorTunable.user_id == actor.user_id)
    )
    quota_bytes = tunable.storage_quota_bytes if tunable else 20 * (2**30)
    used = await s.scalar(
        select(func.coalesce(func.sum(Attachment.bytes), 0)).where(
            Attachment.owner_user_id == actor.user_id,
            Attachment.state.in_(["uploading", "scanning", "clean"]),
        )
    ) or 0
    if used + body.bytes_size > quota_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="quota_exceeded")
    if body.role == "video_primary":
        if tunable and tunable.embed_only:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="embed_only_mode")
        if tunable and not tunable.hosted_video_allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="hosted_video_disabled")

    # Server-generated key. Sanitize filename to prevent path traversal / R2 key tricks.
    import re as _re
    safe_filename = _re.sub(r"[^A-Za-z0-9._-]+", "_", body.filename)[:200] or "file.bin"
    r2_key = f"users/{actor.user_id}/{item.id}/{body.role}/{safe_filename}"
    mpu = await _create_mpu(r2_key, content_type=body.mime)

    att = Attachment(
        owner_user_id=actor.user_id,  # type: ignore[arg-type]
        item_id=item.id,
        role=body.role,
        r2_key=r2_key,
        bytes=body.bytes_size,
        mime=body.mime,
        state="uploading",
    )
    s.add(att)
    await s.flush()

    return CreateUploadOut(
        attachment_id=att.id,
        upload_id=mpu["UploadId"],
        r2_key=r2_key,
        bucket=settings.r2_hot_bucket,
    )


class CompleteIn(BaseModel):
    upload_id: str
    parts: list[dict[str, Any]]


@router.post("/{attachment_id}/complete")
async def complete_upload(
    attachment_id: str,
    body: CompleteIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    att = await s.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if att.owner_user_id != actor.user_id and actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    await _complete(att.r2_key, body.upload_id, body.parts)
    att.state = "scanning"
    # Enqueue scan
    from app.core.redis_client import get_redis
    r = await get_redis()
    await r.lpush("queue:scan", att.id)
    return {"state": "scanning"}


CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB parts — S3 requires >=5 MB except the final.


from contextlib import contextmanager


@contextmanager
def _suppress():
    try:
        yield
    except Exception:
        pass


@router.post("/simple")
async def simple_upload(
    request: Request,
    file: UploadFile,
    item_id: Annotated[str, Form()],
    role: Annotated[str, Form()],
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Streams the upload through the api to R2 using S3 multipart, so memory
    consumption stays ≈ one chunk regardless of file size. Enqueues a ClamAV
    scan after upload. No hard size cap from the api — the effective ceiling
    is the contributor quota plus the reverse-proxy `request_body` limit.
    """
    require_csrf(request)
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="item_not_found")
    try:
        authorize(actor, "item.update", item)
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from e

    if role not in {"video_primary", "article_attachment", "teaching_material_file", "profile_photo"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="bad_role")

    mime = file.content_type or "application/octet-stream"
    if role == "video_primary":
        if mime not in ALLOWED_VIDEO_MIME:
            # Fallback to extension-based detection — Windows often reports
            # `.mov`/`.mkv` as `application/octet-stream`.
            ext = ""
            if file.filename and "." in file.filename:
                ext = "." + file.filename.rsplit(".", 1)[1].lower()
            mapped = VIDEO_EXTENSION_MIME.get(ext)
            if not mapped:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="mime_not_allowed")
            mime = mapped
    elif mime not in ALLOWED_DOC_MIME:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="mime_not_allowed")

    settings = get_settings()

    # Per-contributor knobs. Default quota effectively unlimited at 1 TB.
    tunable = await s.scalar(
        select(ContributorTunable).where(ContributorTunable.user_id == actor.user_id)
    )
    quota_bytes = tunable.storage_quota_bytes if tunable else 1024 * (2**30)
    used = await s.scalar(
        select(func.coalesce(func.sum(Attachment.bytes), 0)).where(
            Attachment.owner_user_id == actor.user_id,
            Attachment.state.in_(["uploading", "scanning", "clean"]),
        )
    ) or 0
    if role == "video_primary":
        if tunable and tunable.embed_only:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="embed_only_mode")
        if tunable and not tunable.hosted_video_allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="hosted_video_disabled")

    import re as _re
    safe_filename = _re.sub(r"[^A-Za-z0-9._-]+", "_", (file.filename or "file.bin"))[:200] or "file.bin"
    r2_key = f"users/{actor.user_id}/{item.id}/{role}/{safe_filename}"

    sess = aioboto3.Session()
    s3_kwargs = {
        "endpoint_url": settings.r2_endpoint_url,
        "region_name": settings.r2_region,
        "aws_access_key_id": settings.r2_access_key_id.get_secret_value(),
        "aws_secret_access_key": settings.r2_secret_access_key.get_secret_value(),
    }

    total_bytes = 0
    parts: list[dict[str, Any]] = []
    async with sess.client("s3", **s3_kwargs) as c:
        mpu = await c.create_multipart_upload(
            Bucket=settings.r2_hot_bucket, Key=r2_key, ContentType=mime
        )
        upload_id = mpu["UploadId"]
        part_num = 1
        buf = bytearray()
        try:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                buf.extend(chunk)
                # Quota enforcement while streaming.
                if used + total_bytes + len(buf) > quota_bytes:
                    with _suppress():
                        await c.abort_multipart_upload(
                            Bucket=settings.r2_hot_bucket, Key=r2_key, UploadId=upload_id
                        )
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="quota_exceeded",
                    )
                while len(buf) >= CHUNK_SIZE:
                    part_body = bytes(buf[:CHUNK_SIZE])
                    del buf[:CHUNK_SIZE]
                    resp = await c.upload_part(
                        Bucket=settings.r2_hot_bucket,
                        Key=r2_key,
                        PartNumber=part_num,
                        UploadId=upload_id,
                        Body=part_body,
                    )
                    parts.append({"PartNumber": part_num, "ETag": resp["ETag"]})
                    part_num += 1
                    total_bytes += len(part_body)
            if buf:
                tail = bytes(buf)
                resp = await c.upload_part(
                    Bucket=settings.r2_hot_bucket,
                    Key=r2_key,
                    PartNumber=part_num,
                    UploadId=upload_id,
                    Body=tail,
                )
                parts.append({"PartNumber": part_num, "ETag": resp["ETag"]})
                total_bytes += len(tail)
            if not parts:
                # Empty body: abort multipart and store a zero-byte object.
                with _suppress():
                    await c.abort_multipart_upload(
                        Bucket=settings.r2_hot_bucket, Key=r2_key, UploadId=upload_id
                    )
                await c.put_object(
                    Bucket=settings.r2_hot_bucket, Key=r2_key, Body=b"", ContentType=mime
                )
            else:
                await c.complete_multipart_upload(
                    Bucket=settings.r2_hot_bucket,
                    Key=r2_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
        except HTTPException:
            raise
        except Exception:
            with _suppress():
                await c.abort_multipart_upload(
                    Bucket=settings.r2_hot_bucket, Key=r2_key, UploadId=upload_id
                )
            raise

    att = Attachment(
        owner_user_id=actor.user_id,  # type: ignore[arg-type]
        item_id=item.id,
        role=role,
        r2_key=r2_key,
        bytes=total_bytes,
        mime=mime,
        state="scanning",
    )
    s.add(att)
    await s.flush()
    # The scan worker is faster than HTTP response teardown — it can BLPOP the
    # ID before the request session commits, then return silently because the
    # row isn't visible yet. Commit before enqueueing so the worker always sees
    # the row.
    await s.commit()

    from app.core.redis_client import get_redis
    r = await get_redis()
    await r.lpush("queue:scan", att.id)

    return {"attachment_id": att.id, "state": att.state, "bytes": total_bytes, "mime": mime, "r2_key": r2_key}


@router.get("/by-item/{item_id}")
async def list_item_attachments(
    item_id: str,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if item.author_id != actor.user_id and actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    rows = (await s.scalars(
        select(Attachment).where(Attachment.item_id == item.id, Attachment.state != "deleted")
    )).all()
    return [
        {
            "id": a.id,
            "role": a.role,
            "mime": a.mime,
            "bytes": a.bytes,
            "state": a.state,
            "r2_key": a.r2_key,
        }
        for a in rows
    ]


@router.delete("/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    require_csrf(request)
    att = await s.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if att.owner_user_id != actor.user_id and actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    try:
        await delete_object(att.r2_key)
    except Exception:
        pass
    att.state = "deleted"
    return {"ok": True}


async def _authorize_attachment_read(
    att: Attachment, actor: Actor, s: AsyncSession
) -> None:
    """Single source of truth for reading attachment *bytes* (stream + url).

    Decision tree:
      * Owner / admin: always allowed (incl. `scanning` state, for preview).
      * `clean` attachment of a `published` item: any authenticated account
        (User / Contributor / Admin). Anonymous → 401 `login_required`.
      * Anything else (draft/pending/quarantined item, non-clean
        attachment, missing parent): 404, with no existence leak.

    The content gate (amended FR-VIDEO-006, 2026-05-20): item / collection /
    author pages and article body text stay public, but the consumable
    payload behind an attachment requires login.
    """
    is_owner = actor.user_id is not None and actor.user_id == att.owner_user_id
    is_admin = actor.role == "admin"
    if is_owner or is_admin:
        return
    # `login_would_help` separates "exists publicly, just needs an account"
    # (→ 401) from "you should not learn this exists" (→ 404, no leak).
    login_would_help = False
    if att.item_id and att.state == "clean":
        parent = await s.scalar(select(Item).where(Item.id == att.item_id))
        if parent and parent.state == "published":
            if actor.user_id is not None:
                return
            login_would_help = True
    if login_would_help:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="login_required")
    raise HTTPException(status.HTTP_404_NOT_FOUND)


@router.get("/{attachment_id}/stream")
async def stream_attachment(
    attachment_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(current_actor)],
    s: Annotated[AsyncSession, Depends(get_session)],
):
    """Stream a clean attachment via the API, supporting HTTP Range.

    Access policy: see `_authorize_attachment_read`.
    """
    from fastapi.responses import StreamingResponse

    att = await s.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if not att or att.state == "deleted":
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    await _authorize_attachment_read(att, actor, s)

    settings = get_settings()
    range_header = request.headers.get("range")

    sess = aioboto3.Session()
    s3_kwargs = {
        "endpoint_url": settings.r2_endpoint_url,
        "region_name": settings.r2_region,
        "aws_access_key_id": settings.r2_access_key_id.get_secret_value(),
        "aws_secret_access_key": settings.r2_secret_access_key.get_secret_value(),
    }

    async def _iter():
        async with sess.client("s3", **s3_kwargs) as c:
            get_kw: dict[str, Any] = {"Bucket": settings.r2_hot_bucket, "Key": att.r2_key}
            if range_header:
                get_kw["Range"] = range_header
            obj = await c.get_object(**get_kw)
            body = obj["Body"]
            try:
                async for chunk in body.iter_chunks(1024 * 64):
                    yield chunk
            finally:
                body.close()

    # Probe once for headers (Content-Length / Content-Range).
    async with sess.client("s3", **s3_kwargs) as c:
        head_kw: dict[str, Any] = {"Bucket": settings.r2_hot_bucket, "Key": att.r2_key}
        if range_header:
            head_kw["Range"] = range_header
        try:
            head = await c.get_object(**head_kw)
        except Exception as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="object_not_found") from e
        # Drain immediately (we re-open in _iter).
        await head["Body"].read()
        # Browser compatibility: .mov (`video/quicktime`) is rejected by Chrome/Firefox
        # even when the inner codec is H.264 (which is what most phones produce).
        # Re-label as `video/mp4` so browsers attempt MP4-family decoding. This is
        # safe: .mov and .mp4 share the ISO BMFF base; tools that strictly require
        # QuickTime metadata can still inspect the bytes.
        ct = att.mime or head.get("ContentType", "application/octet-stream")
        if ct == "video/quicktime":
            ct = "video/mp4"
        headers: dict[str, str] = {
            "Accept-Ranges": "bytes",
            "Content-Type": ct,
        }
        cl = head.get("ContentLength")
        if cl is not None:
            headers["Content-Length"] = str(cl)
        cr = head.get("ContentRange")
        if cr:
            headers["Content-Range"] = cr

    status_code = 206 if range_header else 200
    return StreamingResponse(_iter(), status_code=status_code, headers=headers)


@router.get("/{attachment_id}/url")
async def signed_url(
    attachment_id: str,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Return a short-lived presigned R2 URL for an attachment.

    Uses the same read-authorization as `stream_attachment` so this cannot
    become a side door around the content gate (previously any authenticated
    user could presign any `clean` attachment, including other contributors'
    unpublished drafts).
    """
    att = await s.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if not att or att.state == "deleted":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await _authorize_attachment_read(att, actor, s)
    url = await presign_get(att.r2_key, expires=3600)
    return {"url": url}


async def _clamav_stream_scan(host: str, port: int, source_url: str) -> str | None:
    """Stream `source_url` to clamd's INSTREAM in chunks; return virus name or None.

    Avoids buffering the whole file: each 64 KiB chunk goes straight from
    httpx into the clamd socket. Required for multi-GB uploads — pyclamd's
    `scan_stream(bytes)` would buffer everything in RAM.
    """
    import asyncio
    import struct

    import httpx as _httpx

    CHUNK = 64 * 1024
    reader, writer = await asyncio.open_connection(host, port)
    try:
        # null-prefixed command, per clamd protocol; no terminator on command,
        # the protocol uses length-prefixed chunks ending with a zero length.
        writer.write(b"zINSTREAM\0")
        await writer.drain()

        async with _httpx.AsyncClient(timeout=_httpx.Timeout(60.0, read=600.0)) as c:
            async with c.stream("GET", source_url, follow_redirects=True) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes(chunk_size=CHUNK):
                    if not chunk:
                        continue
                    writer.write(struct.pack(">I", len(chunk)))
                    writer.write(chunk)
                    await writer.drain()
        # zero-length sentinel signals end of stream.
        writer.write(struct.pack(">I", 0))
        await writer.drain()

        # Response is a single line like:
        #   "stream: OK\0" or "stream: Eicar-Test-Signature FOUND\0"
        resp = await reader.readuntil(b"\0")
        text = resp.rstrip(b"\0").decode("utf-8", "replace").strip()
        if text.endswith("OK"):
            return None
        if "FOUND" in text:
            # "stream: Foo FOUND" -> "Foo"
            parts = text.split(":", 1)
            tail = parts[1].strip() if len(parts) > 1 else text
            return tail.removesuffix(" FOUND").strip() or "infected"
        # Unexpected reply (e.g. ERROR) — surface as exception.
        raise RuntimeError(f"clamav_protocol_error: {text}")
    finally:
        with _suppress():
            writer.close()
            await writer.wait_closed()


async def scan_one(attachment_id: str) -> None:
    """Run ClamAV scan against an attachment. Called by worker."""
    import logging

    import pyclamd  # type: ignore[import-untyped]

    from app.core.db import session_scope

    log = logging.getLogger("ndsc.scan")

    async with session_scope() as s:
        att = await s.scalar(select(Attachment).where(Attachment.id == attachment_id))
        if not att:
            # Most often a race: enqueue happened before commit visibility, or
            # the attachment was deleted. Log so this stops being silent.
            log.warning("scan_one: attachment_not_found id=%s", attachment_id)
            return
        settings = get_settings()
        try:
            cd = pyclamd.ClamdNetworkSocket(host=settings.clamav_host, port=settings.clamav_port)
            if not cd.ping():
                raise RuntimeError("clamav_unreachable")
            url = await presign_get(att.r2_key, expires=3600)
            log.info(
                "scan_one: start id=%s bytes=%s mime=%s",
                attachment_id, att.bytes, att.mime,
            )
            virus = await _clamav_stream_scan(
                settings.clamav_host, settings.clamav_port, url
            )
            if virus is None:
                att.state = "clean"
                log.info("scan_one: clean id=%s", attachment_id)
            else:
                att.state = "quarantined"
                await delete_object(att.r2_key)
                log.warning("scan_one: quarantined id=%s virus=%s", attachment_id, virus)
        except Exception as e:
            att.state = "scanning"  # leave for retry
            log.exception("scan_one: failed id=%s err=%s", attachment_id, e)
            raise
