"""Server-side opaque sessions in Redis."""
from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis
from fastapi import Request, Response

from app.core.settings import get_settings


def _session_key(sid: str) -> str:
    return f"session:{sid}"


async def create_session(r: redis.Redis, user_id: str, *, ip: str | None, ua: str | None) -> tuple[str, dict[str, Any]]:
    sid = secrets.token_urlsafe(32)
    s = get_settings()
    data = {
        "user_id": user_id,
        "created_at": datetime.now(UTC).isoformat(),
        "ip": ip,
        "ua": ua,
    }
    await r.set(_session_key(sid), json.dumps(data), ex=s.session_ttl_seconds)
    return sid, data


async def read_session(r: redis.Redis, sid: str) -> dict[str, Any] | None:
    raw = await r.get(_session_key(sid))
    if not raw:
        return None
    return json.loads(raw)


async def touch_session(r: redis.Redis, sid: str) -> None:
    s = get_settings()
    await r.expire(_session_key(sid), s.session_ttl_seconds)


async def destroy_session(r: redis.Redis, sid: str) -> None:
    await r.delete(_session_key(sid))


def set_session_cookie(response: Response, sid: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name,
        sid,
        max_age=s.session_ttl_seconds,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        domain=s.cookie_domain,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        s.session_cookie_name,
        domain=s.cookie_domain,
        path="/",
    )


def session_id_from_request(request: Request) -> str | None:
    s = get_settings()
    return request.cookies.get(s.session_cookie_name)
