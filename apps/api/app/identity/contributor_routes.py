"""Contributor application + role management routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record as audit_record
from app.core.db import get_session
from app.core.policy import Actor, PolicyError, authorize
from app.core.security.csrf import require_csrf
from app.identity.deps import require_admin, require_user
from app.identity.models import ContributorApplication, RoleTransition, User

router = APIRouter(tags=["identity"])


class ApplyIn(BaseModel):
    motivation: str = Field(min_length=20, max_length=5000)
    links: dict | None = None


class ApplyOut(BaseModel):
    id: str
    state: str


@router.post("/me/contributor-application", response_model=ApplyOut)
async def apply(
    body: ApplyIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ApplyOut:
    require_csrf(request)
    user = await s.scalar(select(User).where(User.id == actor.user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if user.role in ("contributor", "admin"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="already_contributor")
    open_ = await s.scalar(
        select(ContributorApplication)
        .where(ContributorApplication.user_id == user.id)
        .order_by(desc(ContributorApplication.created_at))
    )
    if open_ and open_.state == "pending":
        return ApplyOut(id=open_.id, state=open_.state)
    if open_ and open_.state == "rejected":
        if (datetime.now(timezone.utc) - open_.created_at).days < 7:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="cooldown_active")
    app = ContributorApplication(
        user_id=user.id, motivation=body.motivation, links=body.links, state="pending"
    )
    s.add(app)
    await s.flush()  # populate ULID default before serialization
    return ApplyOut(id=app.id, state=app.state)


class DecideIn(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=2000)


@router.post("/admin/applications/{app_id}/decide")
async def decide_application(
    app_id: str,
    body: DecideIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    app = await s.scalar(select(ContributorApplication).where(ContributorApplication.id == app_id))
    if not app or app.state != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    app.state = "approved" if body.approve else "rejected"
    app.decision_actor_id = actor.user_id
    app.decision_reason = body.reason
    app.decided_at = datetime.now(timezone.utc)
    if body.approve:
        user = await s.scalar(select(User).where(User.id == app.user_id))
        if user:
            from_role = user.role
            user.role = "contributor"
            s.add(
                RoleTransition(
                    user_id=user.id,
                    from_role=from_role,
                    to_role="contributor",
                    actor_user_id=actor.user_id,
                    reason=body.reason,
                )
            )
            await audit_record(
                s,
                actor_user_id=actor.user_id,
                actor_ip=request.client.host if request.client else None,
                actor_ua=request.headers.get("user-agent"),
                action="user.role.grant",
                target_type="user",
                target_id=user.id,
                payload={"to_role": "contributor"},
            )
    return {"state": app.state}


class RoleChangeIn(BaseModel):
    role: str = Field(pattern="^(user|contributor|admin)$")
    reason: str | None = None


@router.post("/admin/users/{user_id}/role")
async def change_role(
    user_id: str,
    body: RoleChangeIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    user = await s.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    from_role = user.role
    if from_role == body.role:
        return {"role": body.role}
    user.role = body.role
    s.add(
        RoleTransition(
            user_id=user.id,
            from_role=from_role,
            to_role=body.role,
            actor_user_id=actor.user_id,
            reason=body.reason,
        )
    )
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="user.role.grant" if body.role != "user" else "user.role.revoke",
        target_type="user",
        target_id=user.id,
        payload={"from_role": from_role, "to_role": body.role},
    )
    return {"role": body.role}


class BanIn(BaseModel):
    reason: str | None = None


@router.post("/admin/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    body: BanIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    user = await s.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    user.state = "banned"
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="user.ban",
        target_type="user",
        target_id=user.id,
        payload={"reason": body.reason},
    )
    return {"state": "banned"}
