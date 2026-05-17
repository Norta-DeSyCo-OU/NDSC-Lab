"""CSRF: double-submit cookie. Cookie holds random; header must match."""
from __future__ import annotations

import hmac
import secrets

from fastapi import HTTPException, Request, Response, status

from app.core.settings import get_settings

CSRF_HEADER = "X-CSRF-Token"


def issue_csrf(response: Response) -> str:
    s = get_settings()
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        s.csrf_cookie_name,
        token,
        max_age=s.session_ttl_seconds,
        httponly=False,
        secure=s.cookie_secure,
        samesite="lax",
        domain=s.cookie_domain,
        path="/",
    )
    return token


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    s = get_settings()
    cookie = request.cookies.get(s.csrf_cookie_name)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="csrf_failed"
        )
