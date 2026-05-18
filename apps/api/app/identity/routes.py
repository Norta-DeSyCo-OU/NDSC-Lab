"""HTTP routes for identity (signup, verify, login, logout, forgot, reset, me)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.redis_client import get_redis
from app.core.security import activity_alerts
from app.core.security.csrf import issue_csrf, require_csrf
from app.core.security.signup_flood import SignupCooldownError
from app.core.security.signup_flood import check_and_record as signup_flood_check
from app.identity.deps import require_user
from app.identity.models import User
from app.identity.schemas import (
    ForgotIn,
    GenericOK,
    LoginIn,
    MeOut,
    ResetIn,
    SignupIn,
)
from app.identity.service import (
    LoginError,
    SignupError,
    consume_password_reset,
    consume_verification_token,
    password_login,
    request_password_reset,
    signup,
)
from app.identity.sessions import (
    clear_session_cookie,
    create_session,
    destroy_session,
    session_id_from_request,
    set_session_cookie,
)
from app.notifications.email import send_password_reset_email, send_verification_email

router = APIRouter(prefix="/auth", tags=["identity"])


@router.post("/signup", response_model=GenericOK, status_code=status.HTTP_200_OK)
async def signup_endpoint(
    body: SignupIn,
    request: Request,
    response: Response,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> GenericOK:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    r = await get_redis()
    # Track every attempt (pre-cooldown) so the alerts module sees the burst,
    # not just the ones that survive the flood limiter.
    await activity_alerts.record(r, "signup")
    try:
        await signup_flood_check(r, s, ip=ip, ua=ua)
    except SignupCooldownError as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="signup_cooldown",
            headers={"Retry-After": str(e.retry_after_s)},
        ) from e
    try:
        verify_token = await signup(
            s,
            email=body.email,
            password=body.password,
            age_confirmed=body.age_confirmed,
            tos_version=body.tos_version,
            cookie_consent_version=body.cookie_consent_version,
            analytics_opt_in=body.analytics_opt_in,
            ip=ip,
            ua=ua,
        )
    except SignupError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.code) from e
    if verify_token:
        await send_verification_email(body.email, verify_token)
    issue_csrf(response)
    return GenericOK()


@router.get("/verify", response_model=GenericOK)
async def verify_endpoint(
    t: str,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> GenericOK:
    uid = await consume_verification_token(s, t)
    if not uid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    return GenericOK()


@router.post("/login", response_model=MeOut)
async def login_endpoint(
    body: LoginIn,
    request: Request,
    response: Response,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> MeOut:
    require_csrf(request)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        user = await password_login(
            s, email=body.email, password=body.password, ip=ip, ua=ua
        )
    except LoginError as e:
        # Count failed-login bursts so the alerts module catches credential-spray.
        r2 = await get_redis()
        await activity_alerts.record(r2, "failed_login")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials") from e

    r = await get_redis()
    sid, _ = await create_session(r, user.id, ip=ip, ua=ua)
    set_session_cookie(response, sid)
    issue_csrf(response)
    return MeOut(
        id=user.id,
        email=user.email,
        role=user.role,
        state=user.state,
        display_name=user.display_name,
    )


@router.post("/logout", response_model=GenericOK)
async def logout_endpoint(
    request: Request,
    response: Response,
    _actor=Depends(require_user),  # noqa: B008
) -> GenericOK:
    require_csrf(request)
    sid = session_id_from_request(request)
    if sid:
        r = await get_redis()
        await destroy_session(r, sid)
    clear_session_cookie(response)
    return GenericOK()


@router.post("/forgot", response_model=GenericOK)
async def forgot_endpoint(
    body: ForgotIn,
    request: Request,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> GenericOK:
    require_csrf(request)
    token = await request_password_reset(s, email=body.email)
    if token:
        await send_password_reset_email(body.email, token)
    return GenericOK()


@router.post("/reset", response_model=GenericOK)
async def reset_endpoint(
    body: ResetIn,
    request: Request,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> GenericOK:
    require_csrf(request)
    try:
        ok = await consume_password_reset(s, token=body.token, new_password=body.password)
    except SignupError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.code) from e
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    return GenericOK()


@router.get("/me", response_model=MeOut)
async def me_endpoint(
    actor=Depends(require_user),  # noqa: B008
    s: AsyncSession = Depends(get_session),  # noqa: B008
) -> MeOut:
    from app.curation.models import ContributorProfile

    user = await s.scalar(select(User).where(User.id == actor.user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    profile = await s.scalar(
        select(ContributorProfile).where(ContributorProfile.user_id == user.id)
    )
    return MeOut(
        id=user.id,
        email=user.email,
        role=user.role,
        state=user.state,
        display_name=user.display_name,
        photo_url=f"/api/c/photo/{profile.user_id}"
        if (profile and profile.photo_attachment_id)
        else None,
        profile_slug=profile.slug if profile else None,
    )
