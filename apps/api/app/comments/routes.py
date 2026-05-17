"""Comment routes."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comments.models import Comment, CommentReport
from app.content.markdown import render as md_render
from app.content.models import Item
from app.core.audit import record as audit_record
from app.core.db import get_session
from app.core.policy import Actor, PolicyError, authorize
from app.core.redis_client import get_redis
from app.core.security.csrf import require_csrf
from app.core.security.rate_limit import hit
from app.core.settings import get_settings
from app.identity.deps import require_user

router = APIRouter(tags=["comments"])


class CommentIn(BaseModel):
    body_md: str = Field(min_length=1, max_length=5000)
    parent_id: str | None = None


class CommentOut(BaseModel):
    id: str
    item_id: str
    author_id: str
    parent_id: str | None
    body_md: str
    body_html: str
    state: str
    created_at: datetime
    updated_at: datetime


def _to_out(c: Comment) -> CommentOut:
    return CommentOut(
        id=c.id,
        item_id=c.item_id,
        author_id=c.author_id,
        parent_id=c.parent_id,
        body_md=c.body_md,
        body_html=md_render(c.body_md),
        state=c.state,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post("/items/{item_id}/comments", response_model=CommentOut)
async def post_comment(
    item_id: str,
    body: CommentIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> CommentOut:
    require_csrf(request)
    settings = get_settings()
    r = await get_redis()
    await hit(r, bucket=f"comment:user:{actor.user_id}", limit=settings.rate_limit_comment_per_user_min, window_s=60)

    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        authorize(actor, "comment.create")
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    c = Comment(
        item_id=item_id,
        author_id=actor.user_id,  # type: ignore[arg-type]
        parent_id=body.parent_id,
        body_md=body.body_md,
    )
    s.add(c)
    await s.flush()
    return _to_out(c)


@router.get("/items/{item_id}/comments", response_model=list[CommentOut])
async def list_comments(
    item_id: str,
    s: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
    offset: int = 0,
) -> list[CommentOut]:
    limit = max(1, min(100, limit))
    offset = max(0, offset)
    # D-12: tombstoned items hide comments
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state == "tombstoned":
        return []
    rows = (await s.scalars(
        select(Comment)
        .where(Comment.item_id == item_id, Comment.state == "visible")
        .order_by(Comment.created_at)
        .limit(limit).offset(offset)
    )).all()
    return [_to_out(c) for c in rows]


class CommentPatchIn(BaseModel):
    body_md: str = Field(min_length=1, max_length=5000)


@router.patch("/comments/{comment_id}", response_model=CommentOut)
async def edit_comment(
    comment_id: str,
    body: CommentPatchIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> CommentOut:
    require_csrf(request)
    c = await s.scalar(select(Comment).where(Comment.id == comment_id))
    if not c or c.state != "visible":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        authorize(actor, "comment.update", c)
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    if c.created_at < datetime.now(UTC) - timedelta(minutes=15):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="edit_window_expired")
    c.body_md = body.body_md
    return _to_out(c)


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    require_csrf(request)
    c = await s.scalar(select(Comment).where(Comment.id == comment_id))
    if not c or c.state == "deleted":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        authorize(actor, "comment.delete", c)
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    c.state = "hidden_by_admin" if actor.role == "admin" else "deleted"
    c.deleted_at = datetime.now(UTC)
    if actor.role == "admin":
        await audit_record(
            s,
            actor_user_id=actor.user_id,
            actor_ip=request.client.host if request.client else None,
            actor_ua=request.headers.get("user-agent"),
            action="comment.delete",
            target_type="comment",
            target_id=c.id,
            payload={"item_id": c.item_id, "author_id": c.author_id},
        )
    return {"ok": True}


class ReportIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/comments/{comment_id}/report")
async def report_comment(
    comment_id: str,
    body: ReportIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    require_csrf(request)
    # Rate-limit report abuse.
    r = await get_redis()
    await hit(r, bucket=f"report:user:{actor.user_id}", limit=10, window_s=3600)
    c = await s.scalar(select(Comment).where(Comment.id == comment_id))
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    s.add(CommentReport(comment_id=c.id, reporter_id=actor.user_id, reason=body.reason))
    return {"ok": True}
