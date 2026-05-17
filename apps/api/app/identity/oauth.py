"""Google OAuth 2.0 / OIDC (Authorization Code with PKCE).

Implements FR-AUTH-002.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record as audit_record
from app.core.settings import get_settings
from app.identity.models import OAuthIdentity, User

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"  # noqa: S105
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def make_pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def build_auth_url(*, state: str, code_challenge: str) -> str:
    s = get_settings()
    if not s.google_oauth_client_id:
        raise RuntimeError("google_oauth_not_configured")
    params = {
        "client_id": s.google_oauth_client_id.get_secret_value(),
        "redirect_uri": f"{s.base_url}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH}?{urlencode(params)}"


async def exchange_code(code: str, verifier: str) -> dict[str, Any]:
    s = get_settings()
    if not s.google_oauth_client_id or not s.google_oauth_client_secret:
        raise RuntimeError("google_oauth_not_configured")
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": s.google_oauth_client_id.get_secret_value(),
                "client_secret": s.google_oauth_client_secret.get_secret_value(),
                "redirect_uri": f"{s.base_url}/auth/google/callback",
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
        r.raise_for_status()
        return r.json()


async def fetch_jwks() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(GOOGLE_JWKS)
        r.raise_for_status()
        return r.json()


def _jwt_unverified_segments(token: str) -> tuple[dict, dict]:
    header_b64, payload_b64, _sig_b64 = token.split(".")
    def _pad(s: str) -> str:
        return s + "=" * (-len(s) % 4)
    header = json.loads(base64.urlsafe_b64decode(_pad(header_b64)))
    payload = json.loads(base64.urlsafe_b64decode(_pad(payload_b64)))
    return header, payload


async def verify_id_token(id_token: str) -> dict[str, Any]:
    """Verify Google ID token signature, iss, aud, exp."""
    import time

    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from jwt.algorithms import RSAAlgorithm  # type: ignore[import-untyped]

    s = get_settings()
    header, payload = _jwt_unverified_segments(id_token)
    jwks = await fetch_jwks()
    key_data = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
    if not key_data:
        raise RuntimeError("oidc_kid_unknown")
    pub = RSAAlgorithm.from_jwk(json.dumps(key_data))
    if not isinstance(pub, rsa.RSAPublicKey):
        raise RuntimeError("oidc_pubkey_type")

    import jwt as pyjwt  # type: ignore[import-untyped]

    aud = s.google_oauth_client_id.get_secret_value() if s.google_oauth_client_id else ""
    decoded: dict[str, Any] = pyjwt.decode(
        id_token,
        key=pub,
        algorithms=["RS256"],
        audience=aud,
        issuer=["https://accounts.google.com", "accounts.google.com"],
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    if decoded.get("exp", 0) < int(time.time()):
        raise RuntimeError("oidc_expired")
    return decoded


async def upsert_oauth_user(
    s: AsyncSession,
    *,
    google_sub: str,
    email: str,
    ip: str | None,
    ua: str | None,
    tos_version: str,
    cookie_consent_version: str,
) -> User:
    ident = await s.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == "google", OAuthIdentity.subject == google_sub
        )
    )
    if ident:
        return (await s.scalar(select(User).where(User.id == ident.user_id))) or _crash()

    user_by_email = await s.scalar(select(User).where(User.email == email))
    if user_by_email:
        s.add(OAuthIdentity(user_id=user_by_email.id, provider="google", subject=google_sub))
        return user_by_email

    from datetime import datetime, timezone

    user = User(
        email=email,
        email_verified_at=datetime.now(timezone.utc),
        state="active",
        role="user",
        password_hash=None,
        age_confirmed_at=datetime.now(timezone.utc),
        tos_version=tos_version,
        cookie_consent_version=cookie_consent_version,
    )
    s.add(user)
    await s.flush()
    s.add(OAuthIdentity(user_id=user.id, provider="google", subject=google_sub))
    await audit_record(
        s,
        actor_user_id=user.id,
        actor_ip=ip,
        actor_ua=ua,
        action="user.signup.oauth.google",
        target_type="user",
        target_id=user.id,
        payload={"email": email},
    )
    return user


def _crash() -> User:  # for narrow type
    raise RuntimeError("oauth_user_not_found_post_upsert")
