"""Sliding-window rate limit on Redis ZSET."""
from __future__ import annotations

import secrets
import time

import redis.asyncio as redis
from fastapi import HTTPException, status


async def hit(
    r: redis.Redis,
    *,
    bucket: str,
    limit: int,
    window_s: int,
) -> int:
    """Return current count after adding. Raises 429 if over limit."""
    now = time.time()
    key = f"rl:{bucket}"
    # Unique member token avoids ZADD collision under concurrent requests at the
    # same float second (id(now) was wrong — it's the memory address of a transient).
    member = f"{now}:{secrets.token_hex(8)}"
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_s)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window_s + 5)
    _, _, count, _ = await pipe.execute()
    if int(count) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate_limited"
        )
    return int(count)
