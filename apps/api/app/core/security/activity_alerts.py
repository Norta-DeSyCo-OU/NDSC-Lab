"""Activity-based alert thresholds for admin oversight.

Each "event kind" is tracked in a Redis ZSET sliding window. A periodic
worker reads the windows, compares to per-kind thresholds stored in
`platform_settings`, and emails the platform admins when a window's count
exceeds its threshold.

Alerts have a per-kind cooldown so a sustained event burst doesn't spam
the inbox.

Default thresholds (all overridable via the admin UI / `PlatformSetting`):
    alerts.signup_per_hour       = 30
    alerts.failed_login_per_hour = 50
    alerts.item_publish_per_hour = 20
    alerts.window_s              = 3600
    alerts.cooldown_s            = 21600   (6 h)
    alerts.enabled               = true
"""
from __future__ import annotations

import secrets
import time
from typing import Any

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record as audit_record

KEY_ENABLED = "alerts.enabled"
KEY_SIGNUP = "alerts.signup_per_hour"
KEY_FAILED_LOGIN = "alerts.failed_login_per_hour"
KEY_PUBLISH = "alerts.item_publish_per_hour"
KEY_WINDOW = "alerts.window_s"
KEY_COOLDOWN = "alerts.cooldown_s"

DEFAULTS: dict[str, Any] = {
    KEY_ENABLED: True,
    KEY_SIGNUP: 30,
    KEY_FAILED_LOGIN: 50,
    KEY_PUBLISH: 20,
    KEY_WINDOW: 3600,
    KEY_COOLDOWN: 21600,
}

EVENT_TO_KEY = {
    "signup": KEY_SIGNUP,
    "failed_login": KEY_FAILED_LOGIN,
    "item_publish": KEY_PUBLISH,
}


def _zkey(event: str) -> str:
    return f"alerts:events:{event}"


def _cooldown_key(event: str) -> str:
    return f"alerts:cooldown:{event}"


async def _get_setting(s: AsyncSession, key: str) -> Any:
    from app.legal.models import PlatformSetting

    row = await s.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
    return row.value if row else DEFAULTS[key]


async def record(r: redis.Redis, event: str) -> None:
    """Drop an event timestamp into the sliding window. Cheap, fire-and-forget."""
    if event not in EVENT_TO_KEY:
        return
    now = time.time()
    member = f"{now}:{secrets.token_hex(6)}"
    # Hard ceiling on window expiry; periodic check trims by time anyway.
    pipe = r.pipeline()
    pipe.zadd(_zkey(event), {member: now})
    pipe.expire(_zkey(event), 7 * 24 * 3600)
    await pipe.execute()


async def check_all(r: redis.Redis, s: AsyncSession) -> list[dict[str, Any]]:
    """Iterate event kinds, count within window, fire alerts when exceeded.

    Returns a list of alert dicts that fired (for the worker to email).
    """
    enabled = bool(await _get_setting(s, KEY_ENABLED))
    if not enabled:
        return []

    window_s = int(await _get_setting(s, KEY_WINDOW))
    cooldown_s = int(await _get_setting(s, KEY_COOLDOWN))
    now = time.time()
    fired: list[dict[str, Any]] = []

    for event, threshold_key in EVENT_TO_KEY.items():
        threshold = int(await _get_setting(s, threshold_key))
        # Trim then count.
        await r.zremrangebyscore(_zkey(event), 0, now - window_s)
        count = int(await r.zcard(_zkey(event)))
        if count <= threshold:
            continue

        cooldown_raw = await r.get(_cooldown_key(event))
        if cooldown_raw and float(cooldown_raw) > now:
            continue  # already alerted recently

        await r.set(_cooldown_key(event), str(now + cooldown_s), ex=cooldown_s + 5)
        payload = {
            "event": event,
            "count": count,
            "threshold": threshold,
            "window_s": window_s,
        }
        fired.append(payload)
        try:
            await audit_record(
                s,
                actor_user_id=None,
                actor_ip=None,
                actor_ua=None,
                action="security.activity_alert_triggered",
                target_type="activity_alert",
                target_id=event,
                payload=payload,
            )
        except Exception:
            # Alerting must not block on audit-log issues.
            pass

    return fired


async def status(r: redis.Redis, s: AsyncSession) -> dict[str, Any]:
    """Snapshot for the admin Security page."""
    enabled = bool(await _get_setting(s, KEY_ENABLED))
    window_s = int(await _get_setting(s, KEY_WINDOW))
    cooldown_s = int(await _get_setting(s, KEY_COOLDOWN))
    now = time.time()

    rows = []
    for event, key in EVENT_TO_KEY.items():
        await r.zremrangebyscore(_zkey(event), 0, now - window_s)
        count = int(await r.zcard(_zkey(event)))
        threshold = int(await _get_setting(s, key))
        cooldown_raw = await r.get(_cooldown_key(event))
        cooldown_until = float(cooldown_raw) if cooldown_raw else 0.0
        rows.append({
            "event": event,
            "count": count,
            "threshold": threshold,
            "tripped": count > threshold,
            "cooldown_active": cooldown_until > now,
            "cooldown_remaining_s": int(max(0, cooldown_until - now)),
        })

    return {
        "enabled": enabled,
        "window_s": window_s,
        "cooldown_s": cooldown_s,
        "events": rows,
    }


async def clear_cooldown(r: redis.Redis, event: str | None = None) -> None:
    """Admin "test now" / "reset" action."""
    if event:
        await r.delete(_cooldown_key(event))
    else:
        for ev in EVENT_TO_KEY:
            await r.delete(_cooldown_key(ev))
