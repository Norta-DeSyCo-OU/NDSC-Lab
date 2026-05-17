"""Signed time-limited tokens (verify links, reset links, preview links)."""
from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.settings import get_settings


def _serializer(salt: str) -> URLSafeTimedSerializer:
    s = get_settings()
    return URLSafeTimedSerializer(s.session_signing_key.get_secret_value(), salt=salt)


def issue(salt: str, payload: dict) -> str:
    return _serializer(salt).dumps(payload)


def consume(salt: str, token: str, *, max_age_s: int) -> dict | None:
    try:
        return _serializer(salt).loads(token, max_age=max_age_s)
    except (BadSignature, SignatureExpired):
        return None
