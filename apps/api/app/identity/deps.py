"""FastAPI dependencies: current actor, current user, role gates."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.policy import Actor
from app.core.redis_client import get_redis
from app.identity.models import User
from app.identity.sessions import read_session, session_id_from_request, touch_session


async def current_actor(
    request: Request,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> Actor:
    sid = session_id_from_request(request)
    if not sid:
        return Actor(user_id=None, role=None)
    r = await get_redis()
    data = await read_session(r, sid)
    if not data:
        return Actor(user_id=None, role=None)
    await touch_session(r, sid)
    user_id = data["user_id"]
    user = await s.scalar(select(User).where(User.id == user_id))
    if not user or user.state != "active":
        return Actor(user_id=None, role=None)
    return Actor(user_id=user.id, role=user.role)  # type: ignore[arg-type]


async def require_user(actor: Annotated[Actor, Depends(current_actor)]) -> Actor:
    if actor.user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="auth_required")
    return actor


async def require_admin(actor: Annotated[Actor, Depends(current_actor)]) -> Actor:
    if actor.user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="auth_required")
    if actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="admin_required")
    return actor
