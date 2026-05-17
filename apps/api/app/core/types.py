"""Shared typed primitives."""
from __future__ import annotations

from ulid import ULID


def new_ulid() -> str:
    return str(ULID())
