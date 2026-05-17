"""HaveIBeenPwned k-anonymity password check.

Non-blocking on network failure (logged).
"""
from __future__ import annotations

import hashlib

import httpx

from app.core.telemetry import log

_HIBP_URL = "https://api.pwnedpasswords.com/range/{}"


async def is_pwned(password: str, *, timeout: float = 3.0) -> bool:
    sha1 = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()  # noqa: S324
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(
                _HIBP_URL.format(prefix),
                headers={"Add-Padding": "true", "User-Agent": "ndsc-lab"},
            )
            r.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("hibp_unreachable", error=str(exc))
        return False
    for line in r.text.splitlines():
        h, _, _ = line.partition(":")
        if h.strip().upper() == suffix:
            return True
    return False
