"""Google OAuth HTTP routes."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.redis_client import get_redis
from app.core.security.csrf import issue_csrf
from app.core.settings import get_settings
from app.identity.oauth import (
    build_auth_url,
    exchange_code,
    make_pkce_pair,
    upsert_oauth_user,
    verify_id_token,
)
from app.identity.sessions import create_session, set_session_cookie

router = APIRouter(prefix="/auth/google", tags=["identity"])


_TOS_V = "2026-05-13"
_COOKIE_V = "2026-05-13"


@router.get("/start")
async def start(request: Request) -> RedirectResponse:
    s = get_settings()
    if not s.google_oauth_client_id or not s.google_oauth_client_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="google_oauth_not_configured"
        )
    state = secrets.token_urlsafe(24)
    verifier, challenge = make_pkce_pair()
    r = await get_redis()
    # store state + verifier for 10 min
    await r.set(f"oauth:state:{state}", verifier, ex=600)
    url = build_auth_url(state=state, code_challenge=challenge)
    return RedirectResponse(url)


@router.get("/callback")
async def callback(
    request: Request,
    response: Response,
    state: str,
    code: str | None = None,
    error: str | None = None,
    s: AsyncSession = Depends(get_session),  # noqa: B008
) -> RedirectResponse:
    settings = get_settings()
    if error or not code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=error or "no_code")
    r = await get_redis()
    # GETDEL: atomic single-use consume of the state→verifier mapping.
    # Avoids race where two concurrent callbacks read the same verifier
    # before either delete completes.
    verifier = await r.execute_command("GETDEL", f"oauth:state:{state}")
    if not verifier:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_state")
    tokens = await exchange_code(code, verifier)
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="no_id_token")
    claims = await verify_id_token(id_token)
    if claims.get("email_verified") is not True:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="email_unverified")

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    user = await upsert_oauth_user(
        s,
        google_sub=claims["sub"],
        email=claims["email"],
        ip=ip,
        ua=ua,
        tos_version=_TOS_V,
        cookie_consent_version=_COOKIE_V,
    )
    sid, _ = await create_session(r, user.id, ip=ip, ua=ua)
    redir = RedirectResponse(url=settings.frontend_base_url, status_code=status.HTTP_302_FOUND)
    set_session_cookie(redir, sid)
    issue_csrf(redir)
    return redir
