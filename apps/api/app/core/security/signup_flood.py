"""Global signup-flood detection + cooldown.

Bots scanning the web routinely brute the public `/auth/signup` endpoint, both
to enumerate which emails are already registered and to plant accounts. This
module enforces a global sliding-window count of successful signup *attempts*
(post-validation, pre-account creation) and trips a hard cooldown when the
count exceeds a configurable threshold.

State lives in Redis:
- ZSET `signup:window` — timestamps of recent attempts (TTL = window + 5 s).
- key  `signup:cooldown_until` — unix seconds; if present and in the future,
  every signup attempt is rejected with 429.

Audit log entries with `action='security.signup_flood_triggered'` give admins a
history of when the limiter fired. Admin can clear the cooldown via the API
or disable the limiter entirely via the `signup_flood.enabled` platform
setting.
"""
from __future__ import annotations

import secrets
import time
from typing import Any

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record as audit_record
from app.core.settings import get_settings


# Platform-setting keys (overridable via admin UI).
KEY_ENABLED = "signup_flood.enabled"
KEY_LIMIT = "signup_flood.limit"
KEY_WINDOW_S = "signup_flood.window_s"
KEY_COOLDOWN_S = "signup_flood.cooldown_s"

# Defaults if no platform setting exists. Match the user spec: 20 attempts / 2h.
DEFAULTS = {
    KEY_ENABLED: True,
    KEY_LIMIT: 20,
    KEY_WINDOW_S: 7200,
    KEY_COOLDOWN_S: 1800,
}

WINDOW_KEY = "signup:window"
COOLDOWN_KEY = "signup:cooldown_until"


async def _get_setting(s: AsyncSession, key: str) -> Any:
    from app.legal.models import PlatformSetting  # local import to dodge cycles

    row = await s.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
    if row is None:
        return DEFAULTS[key]
    return row.value


async def status(r: redis.Redis, s: AsyncSession) -> dict[str, Any]:
    """Snapshot of the flood-control state — for the admin dashboard."""
    now = time.time()
    enabled = bool(await _get_setting(s, KEY_ENABLED))
    limit = int(await _get_setting(s, KEY_LIMIT))
    window_s = int(await _get_setting(s, KEY_WINDOW_S))
    cooldown_s = int(await _get_setting(s, KEY_COOLDOWN_S))

    # Trim, then count.
    await r.zremrangebyscore(WINDOW_KEY, 0, now - window_s)
    count = await r.zcard(WINDOW_KEY)

    cooldown_raw = await r.get(COOLDOWN_KEY)
    cooldown_until = float(cooldown_raw) if cooldown_raw else 0.0
    cooldown_active = cooldown_until > now

    return {
        "enabled": enabled,
        "limit": limit,
        "window_s": window_s,
        "cooldown_s": cooldown_s,
        "current_count": int(count),
        "cooldown_active": cooldown_active,
        "cooldown_remaining_s": int(max(0, cooldown_until - now)) if cooldown_active else 0,
    }


async def clear_cooldown(r: redis.Redis) -> None:
    """Admin "release the brake" action."""
    await r.delete(COOLDOWN_KEY)
    await r.delete(WINDOW_KEY)


class SignupCooldownError(Exception):
    """Raised when a signup attempt hits the active cooldown window."""

    def __init__(self, retry_after_s: int):
        self.retry_after_s = retry_after_s
        super().__init__(f"signup_cooldown:{retry_after_s}")


async def check_and_record(
    r: redis.Redis,
    s: AsyncSession,
    *,
    ip: str | None,
    ua: str | None,
) -> None:
    """Increment the window. Trip the cooldown if limit is exceeded.

    Raises `SignupCooldownError` if a cooldown is currently active.
    """
    enabled = bool(await _get_setting(s, KEY_ENABLED))
    if not enabled:
        return

    now = time.time()
    cooldown_raw = await r.get(COOLDOWN_KEY)
    cooldown_until = float(cooldown_raw) if cooldown_raw else 0.0
    if cooldown_until > now:
        raise SignupCooldownError(int(cooldown_until - now))

    limit = int(await _get_setting(s, KEY_LIMIT))
    window_s = int(await _get_setting(s, KEY_WINDOW_S))
    cooldown_s = int(await _get_setting(s, KEY_COOLDOWN_S))

    member = f"{now}:{secrets.token_hex(8)}"
    pipe = r.pipeline()
    pipe.zremrangebyscore(WINDOW_KEY, 0, now - window_s)
    pipe.zadd(WINDOW_KEY, {member: now})
    pipe.zcard(WINDOW_KEY)
    pipe.expire(WINDOW_KEY, window_s + 5)
    _, _, count, _ = await pipe.execute()
    count = int(count)

    if count > limit:
        await r.set(COOLDOWN_KEY, str(now + cooldown_s), ex=cooldown_s + 5)
        await audit_record(
            s,
            actor_user_id=None,
            actor_ip=ip,
            actor_ua=ua,
            action="security.signup_flood_triggered",
            target_type="signup_flood",
            target_id=None,
            payload={
                "count": count,
                "limit": limit,
                "window_s": window_s,
                "cooldown_s": cooldown_s,
            },
        )
        raise SignupCooldownError(cooldown_s)


# Used by uvicorn's Settings dependency for default values exposed via settings.py.
_ = get_settings
