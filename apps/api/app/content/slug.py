"""Slug utilities."""
from __future__ import annotations

import re
import unicodedata

from app.content.models import RESERVED_SLUGS

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def normalize_slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:80]


def is_reserved(slug: str) -> bool:
    return slug in RESERVED_SLUGS
