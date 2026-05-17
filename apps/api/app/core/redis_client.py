"""Async Redis client (sessions, rate limit, dedup, queue)."""
from __future__ import annotations

import redis.asyncio as redis

from app.core.settings import get_settings


def make_redis() -> redis.Redis:
    s = get_settings()
    return redis.from_url(s.redis_url.get_secret_value(), decode_responses=True)


_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = make_redis()
    return _client
