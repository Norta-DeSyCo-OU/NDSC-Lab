"""Data export job — assembles a ZIP and presigns a download URL."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import aioboto3
from sqlalchemy import select

from app.certification.models import Certificate
from app.comments.models import Comment
from app.content.models import Item
from app.core.db import session_scope
from app.core.r2 import presign_get
from app.core.settings import get_settings
from app.core.types import new_ulid
from app.identity.models import User
from app.legal.models import DataExportRequest


async def build_one(req_id: str) -> None:
    settings = get_settings()
    async with session_scope() as s:
        req = await s.scalar(select(DataExportRequest).where(DataExportRequest.id == req_id))
        if not req or req.state != "pending":
            return
        req.state = "building"
        user = await s.scalar(select(User).where(User.id == req.user_id))
        if not user:
            req.state = "expired"
            return

        items = (await s.scalars(select(Item).where(Item.author_id == user.id))).all()
        comments = (await s.scalars(select(Comment).where(Comment.author_id == user.id))).all()
        certs = (await s.scalars(select(Certificate).where(Certificate.user_id == user.id))).all()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(
                "profile.json",
                json.dumps(
                    {
                        "id": user.id,
                        "email": user.email,
                        "display_name": user.display_name,
                        "role": user.role,
                        "state": user.state,
                        "created_at": user.created_at.isoformat(),
                    },
                    indent=2,
                ),
            )
            z.writestr(
                "items.json",
                json.dumps(
                    [
                        {
                            "id": it.id,
                            "type": it.type,
                            "title": it.title,
                            "state": it.state,
                            "body_md": it.body_md,
                            "created_at": it.created_at.isoformat(),
                        }
                        for it in items
                    ],
                    indent=2,
                ),
            )
            z.writestr(
                "comments.json",
                json.dumps(
                    [
                        {
                            "id": c.id,
                            "item_id": c.item_id,
                            "body_md": c.body_md,
                            "created_at": c.created_at.isoformat(),
                            "state": c.state,
                        }
                        for c in comments
                    ],
                    indent=2,
                ),
            )
            z.writestr(
                "certificates.json",
                json.dumps(
                    [
                        {
                            "id": c.id,
                            "collection_id": c.collection_id,
                            "issued_at": c.issued_at.isoformat(),
                            "revoked": c.revoked_at is not None,
                        }
                        for c in certs
                    ],
                    indent=2,
                ),
            )

        # Upload ZIP to R2.
        key = f"exports/{user.id}/{req.id}.zip"
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            region_name=settings.r2_region,
            aws_access_key_id=settings.r2_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        ) as c:
            await c.put_object(
                Bucket=settings.r2_hot_bucket, Key=key, Body=buf.getvalue(), ContentType="application/zip"
            )

        req.state = "ready"
        req.built_at = datetime.now(timezone.utc)
        req.presigned_url_expires_at = req.built_at + timedelta(hours=72)
        await s.flush()
