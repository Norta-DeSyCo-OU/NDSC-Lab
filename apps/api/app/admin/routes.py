"""Admin routes: audit viewer, settings, contributor tunables, announcements."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import desc, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record as audit_record
from app.core.db import get_session
from app.core.policy import Actor, PolicyError, authorize
from app.core.redis_client import get_redis
from app.core.security.csrf import require_csrf
from app.core.security import signup_flood
from app.identity.deps import require_admin
from app.legal.models import ContributorTunable, PlatformSetting

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-log")
async def view_audit(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    actor_user_id: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    limit = max(1, min(500, limit))
    offset = max(0, offset)
    sql = "SELECT id, ts, actor_user_id, action, target_type, target_id, payload FROM audit_log WHERE 1=1"
    params: dict[str, Any] = {}
    if actor_user_id:
        sql += " AND actor_user_id = :actor"
        params["actor"] = actor_user_id
    if action:
        sql += " AND action = :action"
        params["action"] = action
    if target_type:
        sql += " AND target_type = :tt"
        params["tt"] = target_type
    if target_id:
        sql += " AND target_id = :tid"
        params["tid"] = target_id
    sql += " ORDER BY id DESC LIMIT :lim OFFSET :off"
    params["lim"] = limit
    params["off"] = offset
    rows = (await s.execute(text(sql), params)).all()
    return [
        {
            "id": int(r[0]),
            "ts": r[1].isoformat() if r[1] else None,
            "actor_user_id": r[2],
            "action": r[3],
            "target_type": r[4],
            "target_id": r[5],
            "payload": r[6],
        }
        for r in rows
    ]


class SettingIn(BaseModel):
    value: Any


@router.put("/settings/{key}")
async def set_setting(
    key: str,
    body: SettingIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    require_csrf(request)
    try:
        authorize(actor, "platform_setting.write")
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    await s.execute(
        pg_insert(PlatformSetting)
        .values(key=key, value=body.value, updated_by=actor.user_id)
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": body.value, "updated_by": actor.user_id},
        )
    )
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="platform_setting.write",
        target_type="platform_setting",
        target_id=key,
        payload={"value": body.value},
    )
    return {"key": key, "value": body.value}


@router.get("/settings/{key}")
async def get_setting(
    key: str,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await s.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return {"key": row.key, "value": row.value}


class TunableIn(BaseModel):
    storage_quota_bytes: int | None = None
    hosted_video_allowed: bool | None = None
    embed_only: bool | None = None
    max_video_duration_s: int | None = None


@router.put("/contributor-tunables/{user_id}")
async def set_tunable(
    user_id: str,
    body: TunableIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    require_csrf(request)
    try:
        authorize(actor, "contributor_tunable.write")
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    row = await s.scalar(select(ContributorTunable).where(ContributorTunable.user_id == user_id))
    if not row:
        row = ContributorTunable(user_id=user_id)
        s.add(row)
        await s.flush()
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(row, k, v)
    row.updated_by = actor.user_id
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="contributor_tunable.write",
        target_type="user",
        target_id=user_id,
        payload=body.model_dump(exclude_none=True),
    )
    return {"user_id": user_id, **body.model_dump(exclude_none=True)}


# --- signup flood control -------------------------------------------------


@router.get("/signup-flood")
async def signup_flood_status(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    r = await get_redis()
    return await signup_flood.status(r, s)


@router.post("/signup-flood/clear")
async def signup_flood_clear(
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    r = await get_redis()
    await signup_flood.clear_cooldown(r)
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="security.signup_flood_cleared",
        target_type="signup_flood",
        target_id=None,
        payload={},
    )
    return {"ok": "cleared"}
