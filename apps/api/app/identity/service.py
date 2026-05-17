"""Identity service: signup, login, verify, forgot, reset."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record as audit_record
from app.core.redis_client import get_redis
from app.core.security.argon2 import dummy_verify, hash_password, verify_password
from app.core.security.hibp import is_pwned
from app.core.security.rate_limit import hit
from app.core.security.tokens import consume, issue
from app.core.settings import get_settings
from app.identity.models import CookieConsent, LoginAttempt, TosAcceptance, User


class SignupError(Exception):
    code: str

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


async def signup(
    s: AsyncSession,
    *,
    email: str,
    password: str,
    age_confirmed: bool,
    tos_version: str,
    cookie_consent_version: str,
    analytics_opt_in: bool,
    ip: str | None,
    ua: str | None,
) -> str | None:
    """Create user record (idempotent for already-existing email — returns None and silently succeeds)."""
    if await is_pwned(password):
        raise SignupError("password_breached")

    existing = await s.scalar(select(User).where(User.email == email))
    if existing:
        return None  # silent success

    user = User(
        email=email,
        password_hash=hash_password(password),
        age_confirmed_at=datetime.now(UTC),
        tos_version=tos_version,
        cookie_consent_version=cookie_consent_version,
        state="pending_verify",
        role="user",
    )
    s.add(user)
    await s.flush()

    s.add(TosAcceptance(user_id=user.id, tos_version=tos_version, ip=ip))
    s.add(
        CookieConsent(
            user_id=user.id,
            essential=True,
            analytics=analytics_opt_in,
            version=cookie_consent_version,
        )
    )

    await audit_record(
        s,
        actor_user_id=user.id,
        actor_ip=ip,
        actor_ua=ua,
        action="user.signup",
        target_type="user",
        target_id=user.id,
        payload={"email": email},
    )

    return _verify_token_for(user.id)


def _verify_token_for(user_id: str) -> str:
    return issue("auth.verify", {"uid": user_id})


async def consume_verification_token(s: AsyncSession, token: str) -> str | None:
    payload = consume("auth.verify", token, max_age_s=24 * 3600)
    if not payload:
        return None
    user = await s.scalar(select(User).where(User.id == payload["uid"]))
    if not user or user.state == "banned" or user.state == "deleted":
        return None
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        user.state = "active"
    return user.id


class LoginError(Exception):
    pass


async def password_login(
    s: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str | None,
    ua: str | None,
) -> User:
    """Returns active user on success; raises LoginError otherwise."""
    settings = get_settings()
    r = await get_redis()
    await hit(
        r,
        bucket=f"login:ip:{ip or 'none'}",
        limit=settings.rate_limit_login_per_ip_15m,
        window_s=15 * 60,
    )
    await hit(
        r,
        bucket=f"login:acct:{email.lower()}",
        limit=settings.rate_limit_login_per_account_15m,
        window_s=15 * 60,
    )

    user = await s.scalar(select(User).where(User.email == email))
    if not user or user.state != "active" or not user.password_hash:
        dummy_verify(password)  # D-19
        s.add(LoginAttempt(email_lower=email, ip=ip, success=False))
        raise LoginError()

    ok = verify_password(user.password_hash, password)
    s.add(LoginAttempt(email_lower=email, ip=ip, success=ok))
    if not ok:
        raise LoginError()
    return user


async def request_password_reset(s: AsyncSession, *, email: str) -> str | None:
    """Always returns 'success' from caller; returns token when account exists (None otherwise).

    Caller MUST send the email only when a token is returned, AND must respond
    identically to user regardless of return value.
    """
    user = await s.scalar(select(User).where(User.email == email))
    if not user or user.state != "active":
        return None
    return issue("auth.reset", {"uid": user.id})


async def consume_password_reset(s: AsyncSession, *, token: str, new_password: str) -> bool:
    payload = consume("auth.reset", token, max_age_s=3600)
    if not payload:
        return False
    if await is_pwned(new_password):
        raise SignupError("password_breached")
    user = await s.scalar(select(User).where(User.id == payload["uid"]))
    if not user or user.state != "active":
        return False
    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    return True
