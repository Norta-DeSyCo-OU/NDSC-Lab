"""Admin-side content moderation endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.models import Item
from app.content.routes import ItemOut, _to_out
from app.content.service import admin_unpublish, approve_publish, delete_item
from app.core.db import get_session
from app.core.policy import Actor, PolicyError
from app.core.security.csrf import require_csrf
from app.identity.deps import require_admin

router = APIRouter(prefix="/admin/items", tags=["content"])


class RejectIn(BaseModel):
    reason: str


@router.post("/{item_id}/approve", response_model=ItemOut)
async def approve(
    item_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ItemOut:
    require_csrf(request)
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        await approve_publish(
            s, actor=actor, item=item,
            ip=request.client.host if request.client else None,
            ua=request.headers.get("user-agent"),
        )
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    return _to_out(item)


@router.post("/{item_id}/unpublish", response_model=ItemOut)
async def unpublish(
    item_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ItemOut:
    require_csrf(request)
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item or item.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        await admin_unpublish(
            s, actor=actor, item=item,
            ip=request.client.host if request.client else None,
            ua=request.headers.get("user-agent"),
        )
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    return _to_out(item)


@router.delete("/{item_id}", response_model=ItemOut)
async def delete_(
    item_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ItemOut:
    require_csrf(request)
    item = await s.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        await delete_item(
            s, actor=actor, item=item,
            ip=request.client.host if request.client else None,
            ua=request.headers.get("user-agent"),
        )
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    return _to_out(item)
