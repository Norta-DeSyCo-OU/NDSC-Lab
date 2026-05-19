"""Authenticated self-service routes (account-scope)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.certification.models import Certificate
from app.content.models import Item
from app.core.audit import record as audit_record
from app.core.db import get_session
from app.core.policy import Actor
from app.core.security.argon2 import dummy_verify, hash_password, verify_password
from app.core.security.hibp import is_pwned
from app.core.security.tokens import consume, issue
from app.core.settings import get_settings
from app.curation.models import ContributorProfile
from app.identity.deps import require_user
from app.identity.models import ContributorApplication, RoleTransition, User

router = APIRouter(tags=["self"])


# ----- profile read --------------------------------------------------------


class MyProfileOut(BaseModel):
    user_id: str
    slug: str | None
    display_name: str | None
    bio_md: str | None
    affiliation: str | None
    orcid: str | None
    links: list[dict] | None
    contacts: list[dict] | None
    photo_url: str | None
    role: str


@router.get("/me/profile", response_model=MyProfileOut)
async def my_profile(
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> MyProfileOut:
    user = await s.scalar(select(User).where(User.id == actor.user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    p = await s.scalar(select(ContributorProfile).where(ContributorProfile.user_id == user.id))
    return MyProfileOut(
        user_id=user.id,
        slug=p.slug if p else None,
        display_name=user.display_name,
        bio_md=p.bio_md if p else None,
        affiliation=p.affiliation if p else None,
        orcid=p.orcid if p else None,
        links=p.links if p else None,
        contacts=p.contacts if p else None,
        photo_url=f"/api/c/photo/{p.user_id}" if (p and p.photo_attachment_id) else None,
        role=user.role,
    )


# ----- my items ------------------------------------------------------------


class MyItemOut(BaseModel):
    id: str
    type: str
    title: str
    slug: str
    state: str
    summary: str | None
    published_at: datetime | None
    updated_at: datetime


@router.get("/me/items", response_model=list[MyItemOut])
async def my_items(
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MyItemOut]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    stmt = (
        select(Item)
        .where(Item.author_id == actor.user_id)
        .order_by(desc(Item.updated_at))
        .limit(limit)
        .offset(offset)
    )
    if state:
        stmt = stmt.where(Item.state == state)
    rows = (await s.scalars(stmt)).all()
    return [
        MyItemOut(
            id=i.id,
            type=i.type,
            title=i.title,
            slug=i.slug,
            state=i.state,
            summary=i.summary,
            published_at=i.published_at,
            updated_at=i.updated_at,
        )
        for i in rows
    ]


# ----- my certificates -----------------------------------------------------


class MyCertOut(BaseModel):
    id: str
    collection_id: str
    issued_at: datetime
    revoked_at: datetime | None
    signing_key_id: str


@router.get("/me/certificates", response_model=list[MyCertOut])
async def my_certificates(
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> list[MyCertOut]:
    rows = (
        await s.scalars(
            select(Certificate)
            .where(Certificate.user_id == actor.user_id)
            .order_by(desc(Certificate.issued_at))
        )
    ).all()
    return [
        MyCertOut(
            id=c.id,
            collection_id=c.collection_id,
            issued_at=c.issued_at,
            revoked_at=c.revoked_at,
            signing_key_id=c.signing_key_id,
        )
        for c in rows
    ]


# ----- password change / set ----------------------------------------------


class PasswordIn(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=12, max_length=256)


@router.post("/me/password")
async def change_or_set_password(
    body: PasswordIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    user = await s.scalar(select(User).where(User.id == actor.user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    if user.password_hash:
        # General change: require current password.
        if not body.current_password or not verify_password(
            user.password_hash, body.current_password
        ):
            dummy_verify(body.current_password or "")
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="current_password_required")
    else:
        # Set-password flow (FR-AUTH-005 D-01) for OAuth-only accounts:
        # require a recent fresh-OIDC marker.
        from app.core.redis_client import get_redis

        r = await get_redis()
        marker = await r.get(f"oauth:recent:{user.id}")
        if not marker:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="recent_oauth_required")

    if await is_pwned(body.new_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="password_breached")

    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    await audit_record(
        s,
        actor_user_id=user.id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="user.password.change",
        target_type="user",
        target_id=user.id,
        payload={},
    )
    return {"ok": True}


# ----- email change (FR-AUTH-010) -----------------------------------------


class EmailChangeIn(BaseModel):
    new_email: EmailStr
    current_password: str | None = None


@router.post("/me/email")
async def request_email_change(
    body: EmailChangeIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    user = await s.scalar(select(User).where(User.id == actor.user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    if user.password_hash:
        if not body.current_password or not verify_password(user.password_hash, body.current_password):
            dummy_verify(body.current_password or "")
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="current_password_required")
    else:
        from app.core.redis_client import get_redis
        r = await get_redis()
        if not await r.get(f"oauth:recent:{user.id}"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="recent_oauth_required")

    # Check new email not in use.
    existing = await s.scalar(select(User).where(User.email == body.new_email))
    if existing and existing.id != user.id:
        # Account-enumeration defense: return 200 anyway, just don't actually email anyone.
        return {"ok": True}

    # Issue a signed token bound to (user_id, new_email). Confirming the link
    # updates the email + re-sends to old address.
    token = issue("auth.email_change", {"uid": user.id, "new": body.new_email})

    from app.notifications.email import _send  # type: ignore[attr-defined]

    s_settings = get_settings()
    link = f"{s_settings.frontend_base_url}/me/email/confirm?t={token}"
    await _send(
        to=body.new_email,
        subject="NDSC Lab — confirm your new email",
        html=f'<p>Confirm your new email by clicking <a href="{link}">this link</a> (valid 24 h). If you did not request this, ignore the message.</p>',
    )
    if user.email != body.new_email:
        await _send(
            to=user.email,
            subject="NDSC Lab — email change requested",
            html=f"<p>An email change to <strong>{body.new_email}</strong> was requested on your NDSC Lab account. If this wasn't you, change your password and contact support.</p>",
        )
    await audit_record(
        s,
        actor_user_id=user.id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="user.email.request_change",
        target_type="user",
        target_id=user.id,
        payload={"new_email": body.new_email},
    )
    return {"ok": True}


@router.get("/me/email/confirm")
async def confirm_email_change(
    t: str,
    request: Request,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    payload = consume("auth.email_change", t, max_age_s=24 * 3600)
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    user = await s.scalar(select(User).where(User.id == payload["uid"]))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    new_email = payload["new"]
    # Re-check still available.
    other = await s.scalar(select(User).where(User.email == new_email))
    if other and other.id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="email_taken")
    old_email = user.email
    user.email = new_email
    await audit_record(
        s,
        actor_user_id=user.id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="user.email.change",
        target_type="user",
        target_id=user.id,
        payload={"old_email": old_email, "new_email": new_email},
    )
    return {"ok": True}


# ----- contributor self-revoke (FR-ROLE-005) ------------------------------


class RevokeIn(BaseModel):
    confirm: bool
    content_fate: str = Field(pattern="^(tombstone|reassign_house|delete)$")


@router.post("/me/contributor/revoke")
async def self_revoke_contributor(
    body: RevokeIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    if not body.confirm:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="confirm_required")
    user = await s.scalar(select(User).where(User.id == actor.user_id))
    if not user or user.role != "contributor":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="not_a_contributor")
    from_role = user.role
    user.role = "user"
    s.add(
        RoleTransition(
            user_id=user.id,
            from_role=from_role,
            to_role="user",
            actor_user_id=user.id,
            reason=f"self_revoke:{body.content_fate}",
        )
    )
    # Tombstone all items for now; admin can reverse via reassign-to-house later.
    from sqlalchemy import update
    if body.content_fate in ("tombstone", "reassign_house"):
        await s.execute(
            update(Item).where(Item.author_id == user.id).values(state="tombstoned",
                                                                  deleted_at=datetime.now(UTC))
        )
    await audit_record(
        s,
        actor_user_id=user.id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="user.role.revoke.self",
        target_type="user",
        target_id=user.id,
        payload={"content_fate": body.content_fate},
    )
    return {"ok": True}


# ----- contributor application status -------------------------------------


class ApplicationStatusOut(BaseModel):
    id: str | None
    state: str | None
    motivation: str | None
    decision_reason: str | None
    created_at: datetime | None


@router.get("/me/contributor-application", response_model=ApplicationStatusOut)
async def my_application(
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ApplicationStatusOut:
    a = await s.scalar(
        select(ContributorApplication)
        .where(ContributorApplication.user_id == actor.user_id)
        .order_by(desc(ContributorApplication.created_at))
    )
    if not a:
        return ApplicationStatusOut(id=None, state=None, motivation=None,
                                     decision_reason=None, created_at=None)
    return ApplicationStatusOut(
        id=a.id, state=a.state, motivation=a.motivation,
        decision_reason=a.decision_reason, created_at=a.created_at,
    )
