"""Content HTTP routes."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.models import Category, Item, Tag
from app.content.service import ContentError, create_draft, submit_for_review, update_draft
from app.core.db import get_session
from app.core.policy import Actor, PolicyError, authorize
from app.core.security.csrf import require_csrf
from app.identity.deps import current_actor, require_user

router = APIRouter(prefix="/items", tags=["content"])


class CreateIn(BaseModel):
    type: str = Field(pattern="^(video|article|teaching_material)$")
    title: str = Field(min_length=3, max_length=200)
    body_md: str | None = Field(default=None, max_length=200_000)
    summary: str | None = Field(default=None, max_length=2000)
    external_url: str | None = None
    video_kind: str | None = Field(default=None, pattern="^(hosted|embed)$")
    license: str = "cc-by-4.0"


class UpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    body_md: str | None = Field(default=None, max_length=200_000)
    summary: str | None = Field(default=None, max_length=2000)
    external_url: str | None = None
    video_kind: str | None = Field(default=None, pattern="^(hosted|embed)$")
    license: str | None = Field(
        default=None, pattern="^(cc-by-4.0|cc-by-sa-4.0|cc-by-nc-4.0|cc0-1.0|arr)$"
    )


class ItemOut(BaseModel):
    id: str
    author_id: str
    author_slug: str | None = None
    author_display_name: str | None = None
    type: str
    title: str
    slug: str
    state: str
    summary: str | None
    body_html: str | None
    license: str
    published_at: datetime | None
    video_kind: str | None
    external_url: str | None


def _to_out(item: Item, author_slug: str | None = None, author_display_name: str | None = None) -> ItemOut:
    return ItemOut(
        id=item.id,
        author_id=item.author_id,
        author_slug=author_slug,
        author_display_name=author_display_name,
        type=item.type,
        title=item.title,
        slug=item.slug,
        state=item.state,
        summary=item.summary,
        body_html=item.body_html_cached,
        license=item.license,
        published_at=item.published_at,
        video_kind=item.video_kind,
        external_url=item.external_url,
    )


async def _author_info_for(s, author_ids: list[str]) -> dict[str, tuple[str | None, str | None]]:
    """Returns {author_id: (slug, display_name)} for the requested ids."""
    from app.curation.models import ContributorProfile
    from app.identity.models import User

    if not author_ids:
        return {}
    uniq = list(set(author_ids))
    rows = (
        await s.execute(
            select(User.id, User.display_name, ContributorProfile.slug)
            .join(ContributorProfile, ContributorProfile.user_id == User.id, isouter=True)
            .where(User.id.in_(uniq))
        )
    ).all()
    return {uid: (slug, dn) for uid, dn, slug in rows}


@router.post("", response_model=ItemOut)
async def create(
    body: CreateIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ItemOut:
    require_csrf(request)
    # Embed videos must carry a real URL — saving an empty embed produces a
    # broken item that renders an empty player (FR-VIDEO-008).
    if body.type == "video" and body.video_kind == "embed" and not body.external_url:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="embed_url_required"
        )
    try:
        item = await create_draft(
            s,
            actor=actor,
            type_=body.type,
            title=body.title,
            body_md=body.body_md,
            summary=body.summary,
            external_url=body.external_url,
            video_kind=body.video_kind,
            license=body.license,
        )
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from e
    except ContentError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.code) from e
    return _to_out(item)


@router.patch("/{item_id}", response_model=ItemOut)
async def update(
    item_id: str,
    body: UpdateIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ItemOut:
    require_csrf(request)
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        await update_draft(
            s,
            actor=actor,
            item=item,
            title=body.title,
            body_md=body.body_md,
            summary=body.summary,
            external_url=body.external_url,
            video_kind=body.video_kind,
            license=body.license,
        )
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from e
    return _to_out(item)


@router.post("/{item_id}/submit", response_model=ItemOut)
async def submit(
    item_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ItemOut:
    require_csrf(request)
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        await submit_for_review(s, actor=actor, item=item)
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from e
    except ContentError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.code) from e
    return _to_out(item)


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(
    item_id: str,
    actor: Annotated[Actor, Depends(current_actor)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ItemOut:
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if item.state != "published":
        try:
            authorize(actor, "item.read.draft", item)
        except PolicyError as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND) from e  # don't leak existence
    info = await _author_info_for(s, [item.author_id])
    slug, dn = info.get(item.author_id, (None, None))
    return _to_out(item, author_slug=slug, author_display_name=dn)


class ItemRawOut(BaseModel):
    """FR-CONTENT-012a: author/admin-only raw source view."""

    id: str
    author_id: str
    type: str
    title: str
    slug: str
    state: str
    summary: str | None
    body_md: str | None
    external_url: str | None
    video_kind: str | None
    license: str


@router.get("/{item_id}/raw", response_model=ItemRawOut)
async def get_item_raw(
    item_id: str,
    actor: Annotated[Actor, Depends(current_actor)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ItemRawOut:
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if not (actor.role == "admin" or item.author_id == actor.user_id):
        # Non-owner non-admin: don't even confirm existence.
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return ItemRawOut(
        id=item.id,
        author_id=item.author_id,
        type=item.type,
        title=item.title,
        slug=item.slug,
        state=item.state,
        summary=item.summary,
        body_md=item.body_md,
        external_url=item.external_url,
        video_kind=item.video_kind,
        license=item.license,
    )


@router.get("/{item_id}/attachments")
async def list_item_attachments_public(
    item_id: str,
    actor: Annotated[Actor, Depends(current_actor)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    """Public-by-default listing of clean attachments for a published item.

    Owners + admins see all roles + all states. Anonymous viewers only see
    `clean` attachments on a `published` item, and only safe roles (video,
    teaching material, article attachments). The url field is `/api/uploads/{id}/stream`.
    """
    from app.content.models import Attachment

    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    can_see_all = actor.role == "admin" or item.author_id == actor.user_id
    if not can_see_all and item.state != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    rows = (
        await s.scalars(select(Attachment).where(Attachment.item_id == item_id))
    ).all()
    out = []
    for a in rows:
        if not can_see_all:
            if a.state != "clean":
                continue
            if a.role not in (
                "video_primary",
                "video_transcoded",
                "teaching_material_file",
                "article_attachment",
                "video_thumbnail",
            ):
                continue
        out.append(
            {
                "id": a.id,
                "role": a.role,
                "mime": a.mime,
                "bytes": a.bytes,
                "state": a.state,
                "stream_url": f"/api/uploads/{a.id}/stream",
            }
        )
    return out


@router.get("", response_model=list[ItemOut])
async def list_items(
    actor: Annotated[Actor, Depends(current_actor)],
    s: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = None,
    type: str | None = None,
    contributor: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[ItemOut]:
    """Filtered list. D-10: only published unless viewer is author or admin."""
    limit = max(1, min(50, limit))
    offset = max(0, offset)

    conditions = []
    if actor.role == "admin":
        conditions.append(Item.state != "tombstoned")
    elif actor.user_id:
        conditions.append(
            or_(
                Item.state == "published",
                and_(Item.author_id == actor.user_id, Item.state != "tombstoned"),
            )
        )
    else:
        conditions.append(Item.state == "published")

    if type:
        conditions.append(Item.type == type)
    if contributor:
        conditions.append(Item.author_id == contributor)
    if q:
        # Postgres FTS (FR-SEARCH-001). search_vector is a generated/maintained column.
        conditions.append(Item.search_vector.op("@@")(_websearch_to_tsquery(q)))

    stmt = (
        select(Item).where(and_(*conditions)).order_by(Item.published_at.desc().nullslast()).limit(limit).offset(offset)
    )
    rows = (await s.scalars(stmt)).all()
    info = await _author_info_for(s, [r.author_id for r in rows])
    out: list[ItemOut] = []
    for r in rows:
        slug, dn = info.get(r.author_id, (None, None))
        out.append(_to_out(r, author_slug=slug, author_display_name=dn))
    return out


def _websearch_to_tsquery(q: str):
    from sqlalchemy import func
    return func.websearch_to_tsquery("english", q)
