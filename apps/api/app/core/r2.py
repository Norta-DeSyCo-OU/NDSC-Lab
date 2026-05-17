"""S3-compatible client for Cloudflare R2."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3

from app.core.settings import get_settings


@asynccontextmanager
async def r2_client() -> AsyncIterator[Any]:
    s = get_settings()
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=s.r2_endpoint_url,
        region_name=s.r2_region,
        aws_access_key_id=s.r2_access_key_id.get_secret_value(),
        aws_secret_access_key=s.r2_secret_access_key.get_secret_value(),
    ) as c:
        yield c


async def presign_get(key: str, *, bucket: str | None = None, expires: int = 3600) -> str:
    s = get_settings()
    b = bucket or s.r2_hot_bucket
    async with r2_client() as c:
        return await c.generate_presigned_url(
            "get_object",
            Params={"Bucket": b, "Key": key},
            ExpiresIn=expires,
        )


async def presign_put(key: str, *, bucket: str | None = None, expires: int = 3600) -> str:
    s = get_settings()
    b = bucket or s.r2_hot_bucket
    async with r2_client() as c:
        return await c.generate_presigned_url(
            "put_object",
            Params={"Bucket": b, "Key": key},
            ExpiresIn=expires,
        )


async def create_multipart_upload(key: str, *, bucket: str | None = None, content_type: str = "application/octet-stream") -> dict[str, Any]:
    s = get_settings()
    b = bucket or s.r2_hot_bucket
    async with r2_client() as c:
        return await c.create_multipart_upload(Bucket=b, Key=key, ContentType=content_type)


async def complete_multipart_upload(key: str, upload_id: str, parts: list[dict[str, Any]], *, bucket: str | None = None) -> None:
    s = get_settings()
    b = bucket or s.r2_hot_bucket
    async with r2_client() as c:
        await c.complete_multipart_upload(
            Bucket=b, Key=key, UploadId=upload_id, MultipartUpload={"Parts": parts}
        )


async def delete_object(key: str, *, bucket: str | None = None) -> None:
    s = get_settings()
    b = bucket or s.r2_hot_bucket
    async with r2_client() as c:
        await c.delete_object(Bucket=b, Key=key)
