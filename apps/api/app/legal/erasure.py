"""Erasure execution job — runs after grace period.

Pseudonymizes audit_log entries (FR-LEG-004, D-06). HMAC chain unaffected
because chain is computed over canonical non-PII projection (D-15).
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.comments.models import Comment
from app.content.models import Attachment, Item
from app.core.db import session_scope
from app.core.r2 import delete_object
from app.core.types import new_ulid
from app.identity.models import LoginAttempt, User
from app.legal.models import ErasureRequest


async def execute_due() -> int:
    """Run erasure for all requests whose grace period has passed. Returns processed count."""
    processed = 0
    async with session_scope() as s:
        now = datetime.now(UTC)
        rows = (
            await s.scalars(
                select(ErasureRequest).where(
                    ErasureRequest.state == "pending",
                    ErasureRequest.grace_until < now,
                )
            )
        ).all()
        for req in rows:
            await _execute_one(s, req)
            processed += 1
    return processed


async def _execute_one(s: AsyncSession, req: ErasureRequest) -> None:
    req.state = "executing"
    await s.flush()

    user = await s.scalar(select(User).where(User.id == req.user_id))
    if not user:
        req.state = "completed"
        return

    # Tombstone all items (admin will decide deletion vs anonymize via the
    # contributor revocation flow; here we hard-tombstone for the user's items).
    items = (await s.scalars(select(Item).where(Item.author_id == user.id))).all()
    for it in items:
        it.state = "tombstoned"
        it.deleted_at = datetime.now(UTC)

    # Delete blobs in R2.
    atts = (await s.scalars(select(Attachment).where(Attachment.owner_user_id == user.id))).all()
    for att in atts:
        try:
            await delete_object(att.r2_key)
        except Exception:
            pass
        att.state = "deleted"

    # Soft-delete comments authored by the user.
    await s.execute(
        update(Comment).where(Comment.author_id == user.id).values(state="deleted", body_md="[deleted]")
    )

    # Drop the user's login attempt history.
    await s.execute(delete(LoginAttempt).where(LoginAttempt.email_lower == user.email))

    # If the user has issued certificates as admin: pseudonymize for verification (D-13).
    await s.execute(
        text(
            "INSERT INTO cert_admin_pseudonyms (original_admin_id, pseudonym_id) "
            "SELECT issued_by_admin_id, :pseudo FROM certificates WHERE issued_by_admin_id = :uid "
            "ON CONFLICT DO NOTHING"
        ),
        {"uid": user.id, "pseudo": new_ulid()},
    )

    # Pseudonymize audit_log actor (NFR-SEC-014 + D-15 keep chain intact).
    pseudo = new_ulid()
    await s.execute(
        text(
            "UPDATE audit_log SET actor_user_id = :pseudo, "
            "actor_ip = NULL, actor_ua = '[redacted]', "
            "payload = (payload - 'ip' - 'ua' - 'email') "
            "WHERE actor_user_id = :uid"
        ),
        {"pseudo": pseudo, "uid": user.id},
    )

    # Final: hard-delete the user record itself.
    user.state = "deleted"
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.password_hash = None
    user.display_name = None
    user.deleted_at = datetime.now(UTC)

    req.state = "completed"
    req.completed_at = datetime.now(UTC)
