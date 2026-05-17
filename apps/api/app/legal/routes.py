"""Legal HTTP routes: takedown, erasure, data export."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record as audit_record
from app.core.db import get_session
from app.core.policy import Actor, PolicyError, authorize
from app.core.security.argon2 import verify_password
from app.core.security.csrf import require_csrf
from app.identity.deps import require_admin, require_user
from app.identity.models import User
from app.legal.models import DataExportRequest, ErasureRequest, TakedownRequest

router = APIRouter(tags=["legal"])


# -- Takedown ----------------------------------------------------------------

class TakedownIn(BaseModel):
    complainant_name: str = Field(min_length=2, max_length=200)
    complainant_email: EmailStr
    complainant_address: str | None = Field(default=None, max_length=500)
    target_url: HttpUrl
    sworn_statement: str = Field(min_length=20, max_length=5000)


@router.post("/legal/takedown")
async def submit_takedown(
    body: TakedownIn,
    request: Request,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    t = TakedownRequest(
        complainant_name=body.complainant_name,
        complainant_email=body.complainant_email,
        complainant_address=body.complainant_address,
        target_url=str(body.target_url),
        sworn_statement=body.sworn_statement,
    )
    s.add(t)
    await s.flush()
    return {"id": t.id, "state": t.state}


class TakedownDecisionIn(BaseModel):
    action: str = Field(pattern="^(tombstone|reject)$")
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/admin/takedowns/{t_id}/decide")
async def decide_takedown(
    t_id: str,
    body: TakedownDecisionIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    t = await s.scalar(select(TakedownRequest).where(TakedownRequest.id == t_id))
    if not t or t.state != "open":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        authorize(actor, "takedown.decide")
    except PolicyError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e
    t.state = "closed_tombstoned" if body.action == "tombstone" else "closed_rejected"
    t.decision_actor_id = actor.user_id
    t.decision_reason = body.reason
    t.decided_at = datetime.now(UTC)
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="takedown.decide",
        target_type="takedown",
        target_id=t.id,
        payload={"action": body.action, "reason": body.reason},
    )
    return {"state": t.state}


# -- Erasure -----------------------------------------------------------------

class ErasureIn(BaseModel):
    password: str | None = None


@router.post("/me/erasure")
async def request_erasure(
    body: ErasureIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    user = await s.scalar(select(User).where(User.id == actor.user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # Rate-limit erasure-confirm attempts (prevents grace-window brute-force).
    from app.core.redis_client import get_redis
    from app.core.security.rate_limit import hit as _rl_hit

    r = await get_redis()
    await _rl_hit(r, bucket=f"erasure:user:{user.id}", limit=5, window_s=3600)

    # Require password re-confirm for password users; OAuth-only users must complete a fresh
    # OIDC step in the UI, which writes a marker to Redis (key oauth:recent:<user_id>, TTL 10 min).
    if user.password_hash:
        if not body.password or not verify_password(user.password_hash, body.password):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="password_required")
    else:
        marker = await r.get(f"oauth:recent:{user.id}")
        if not marker:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="recent_oauth_required")
    now = datetime.now(UTC)
    e = ErasureRequest(
        user_id=user.id,
        state="pending",
        grace_until=now + timedelta(days=7),
        eta_at=now + timedelta(days=30),
    )
    s.add(e)
    return {"state": "pending", "grace_until": e.grace_until.isoformat()}


@router.post("/me/erasure/cancel")
async def cancel_erasure(
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    require_csrf(request)
    e = await s.scalar(
        select(ErasureRequest).where(
            ErasureRequest.user_id == actor.user_id, ErasureRequest.state == "pending"
        )
    )
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if e.grace_until < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="grace_expired")
    e.state = "cancelled"
    return {"ok": True}


# -- Data export -------------------------------------------------------------

@router.post("/me/export")
async def request_data_export(
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    open_ = await s.scalar(
        select(DataExportRequest).where(
            DataExportRequest.user_id == actor.user_id,
            DataExportRequest.state.in_(["pending", "building"]),
        )
    )
    if open_:
        return {"id": open_.id, "state": open_.state}
    req = DataExportRequest(user_id=actor.user_id, state="pending")  # type: ignore[arg-type]
    s.add(req)
    await s.flush()
    from app.core.redis_client import get_redis
    r = await get_redis()
    await r.lpush("queue:export", req.id)
    return {"id": req.id, "state": req.state}
