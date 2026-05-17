"""Tamper-evident audit log.

HMAC chain computed over a *canonical non-PII projection* (D-15), so PII columns
can be pseudonymized post-hoc without breaking the chain.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings


def _canon(*, action: str, target_type: str, target_id: str, ts_epoch: float, payload_pruned: dict[str, Any]) -> str:
    return json.dumps(
        {
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "ts_epoch": ts_epoch,
            "payload_pruned": payload_pruned,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _prune_pii(payload: dict[str, Any]) -> dict[str, Any]:
    PII = {"ip", "ua", "email", "user_agent"}
    return {k: v for k, v in payload.items() if k not in PII}


async def record(
    s: AsyncSession,
    *,
    actor_user_id: str | None,
    actor_ip: str | None,
    actor_ua: str | None,
    action: str,
    target_type: str,
    target_id: str,
    payload: dict[str, Any] | None = None,
) -> None:
    ts = datetime.now(UTC)
    payload = payload or {}
    canon = _canon(
        action=action,
        target_type=target_type,
        target_id=target_id,
        ts_epoch=ts.timestamp(),
        payload_pruned=_prune_pii(payload),
    )

    key = get_settings().audit_hmac_key.get_secret_value().encode()
    prev = await s.execute(
        text("SELECT hmac FROM audit_log ORDER BY id DESC LIMIT 1")
    )
    prev_hmac = prev.scalar_one_or_none()
    if isinstance(prev_hmac, memoryview):
        base = prev_hmac.tobytes()
    elif isinstance(prev_hmac, bytes | bytearray):
        base = bytes(prev_hmac)
    elif isinstance(prev_hmac, str):
        base = bytes.fromhex(prev_hmac)
    else:
        base = b""
    chained = hmac.new(key, base + canon.encode(), hashlib.sha256).digest()

    full_payload = {**payload, "ip": actor_ip, "ua": actor_ua}

    await s.execute(
        text(
            """
            INSERT INTO audit_log
              (ts, actor_user_id, actor_ip, actor_ua, action, target_type, target_id, payload, prev_hmac, hmac)
            VALUES
              (:ts, :uid, :ip, :ua, :action, :ttype, :tid, CAST(:payload AS jsonb), :prev, :hmac)
            """
        ),
        {
            "ts": ts,
            "uid": actor_user_id,
            "ip": actor_ip,
            "ua": actor_ua,
            "action": action,
            "ttype": target_type,
            "tid": str(target_id),
            "payload": json.dumps(full_payload),
            "prev": base if base else None,
            "hmac": chained,
        },
    )
