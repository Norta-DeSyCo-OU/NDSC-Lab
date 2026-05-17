"""Content service: item state machine."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.markdown import render as md_render
from app.content.models import Attachment, Item, ReviewSubmission
from app.content.slug import is_reserved, normalize_slug
from app.core.audit import record as audit_record
from app.core.policy import Actor, authorize


class ContentError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


async def create_draft(
    s: AsyncSession,
    *,
    actor: Actor,
    type_: str,
    title: str,
    body_md: str | None,
    summary: str | None,
    external_url: str | None,
    video_kind: str | None,
    license: str = "cc-by-4.0",
) -> Item:
    authorize(actor, "item.create")
    if not actor.user_id:
        raise ContentError("auth_required")
    slug = normalize_slug(title) or "untitled"
    if is_reserved(slug):
        slug = f"{slug}-item"

    # uniqueness per author
    n = 0
    base = slug
    while await s.scalar(
        select(Item).where(Item.author_id == actor.user_id, Item.slug == slug)
    ):
        n += 1
        slug = f"{base}-{n}"

    item = Item(
        author_id=actor.user_id,
        type=type_,
        video_kind=video_kind,
        title=title,
        slug=slug,
        summary=summary,
        body_md=body_md,
        body_html_cached=md_render(body_md) if body_md else None,
        external_url=external_url,
        license=license,
        state="draft",
    )
    s.add(item)
    await s.flush()
    return item


async def update_draft(
    s: AsyncSession,
    *,
    actor: Actor,
    item: Item,
    title: str | None,
    body_md: str | None,
    summary: str | None,
    external_url: str | None = None,
    video_kind: str | None = None,
    license: str | None = None,
) -> Item:
    authorize(actor, "item.update", item)
    if title is not None:
        item.title = title
    if summary is not None:
        item.summary = summary
    if body_md is not None:
        item.body_md = body_md
        item.body_html_cached = md_render(body_md)
    if external_url is not None:
        item.external_url = external_url or None
    if video_kind is not None and item.type == "video":
        item.video_kind = video_kind
    if license is not None:
        item.license = license
    item.updated_at = datetime.now(timezone.utc)
    return item


async def submit_for_review(s: AsyncSession, *, actor: Actor, item: Item) -> None:
    authorize(actor, "item.submit", item)
    # Hosted-video items must have a clean attachment present.
    if item.type == "video" and item.video_kind == "hosted":
        att = await s.scalar(
            select(Attachment).where(Attachment.item_id == item.id, Attachment.role == "video_primary")
        )
        if not att or att.state != "clean":
            raise ContentError("video_attachment_not_clean")
    # Embed-video items must have an external_url set, otherwise the public
    # player has no source and renders an empty box (FR-VIDEO-008).
    if item.type == "video" and item.video_kind == "embed":
        if not item.external_url:
            raise ContentError("embed_url_required")
    item.state = "pending_review"
    s.add(ReviewSubmission(item_id=item.id, submitted_by=actor.user_id))  # type: ignore[arg-type]


async def approve_publish(
    s: AsyncSession,
    *,
    actor: Actor,
    item: Item,
    ip: str | None,
    ua: str | None,
) -> None:
    authorize(actor, "item.publish", item)
    item.state = "published"
    item.published_at = datetime.now(timezone.utc)
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=ip,
        actor_ua=ua,
        action="item.publish",
        target_type="item",
        target_id=item.id,
        payload={"author_id": item.author_id},
    )


async def admin_unpublish(
    s: AsyncSession,
    *,
    actor: Actor,
    item: Item,
    ip: str | None,
    ua: str | None,
) -> None:
    authorize(actor, "item.publish", item)  # publish gate covers unpublish (admin only)
    item.state = "draft"
    item.published_at = None
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=ip,
        actor_ua=ua,
        action="item.unpublish",
        target_type="item",
        target_id=item.id,
        payload={},
    )


async def delete_item(
    s: AsyncSession,
    *,
    actor: Actor,
    item: Item,
    ip: str | None,
    ua: str | None,
) -> None:
    authorize(actor, "item.delete", item)
    item.state = "tombstoned"
    item.deleted_at = datetime.now(timezone.utc)
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=ip,
        actor_ua=ua,
        action="item.delete",
        target_type="item",
        target_id=item.id,
        payload={"author_id": item.author_id},
    )
